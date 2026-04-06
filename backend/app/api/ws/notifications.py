"""
WebSocket Notification System — Redis Pub/Sub Architecture
==========================================================

Instead of polling the DB every 1.5s per connected client, we now:
1. On connect: do a ONE-TIME DB catch-up for missed notifications.
2. Then subscribe to a Redis pub/sub channel `notifications:{user_id}`.
3. Celery tasks publish to the same channel after persisting notifications.

Additional hardening:
- Per-user connection limit (default 5)
- Ping/pong heartbeat (30s) to detect stale connections
- General exception handler to prevent silent drops
"""

import asyncio
import json
import logging
from typing import Dict

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.db.models.notification import Notification
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Redis connection pool (shared across all WS connections) ──────────────
_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Lazy-initialize a shared Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        redis_url = settings.REDIS_URL
        _redis_pool = aioredis.from_url(redis_url, decode_responses=True)
    return _redis_pool


async def publish_notification(user_id: int, message: dict) -> None:
    """Publish a notification to the Redis channel for a specific user.
    Called from Celery tasks (via sync wrapper) or from FastAPI code.
    """
    try:
        r = await get_redis()
        channel = f"notifications:{user_id}"
        await r.publish(channel, json.dumps(message, default=str))
        logger.debug("[Redis Pub] Published to %s", channel)
    except Exception as e:
        logger.warning("[Redis Pub] Failed to publish to user %s: %s", user_id, e)


def publish_notification_sync(user_id: int, message: dict) -> None:
    """Synchronous wrapper for publishing from Celery tasks.
    Creates a one-shot event loop to publish.
    """
    import redis as sync_redis

    try:
        redis_url = settings.REDIS_URL
        r = sync_redis.from_url(redis_url, decode_responses=True)
        channel = f"notifications:{user_id}"
        r.publish(channel, json.dumps(message, default=str))
        r.close()
        logger.debug("[Redis Pub Sync] Published to %s", channel)
    except Exception as e:
        logger.warning("[Redis Pub Sync] Failed to publish to user %s: %s", user_id, e)


# ── Connection Manager ────────────────────────────────────────────────────


class NotificationConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        """Accept and register a WebSocket. Returns False if limit exceeded."""
        max_conns = settings.WS_MAX_CONNECTIONS_PER_USER

        current = self.active_connections.get(user_id, [])
        if len(current) >= max_conns:
            logger.warning(
                "[WS] User %s already has %d connections (max=%d), rejecting",
                user_id, len(current), max_conns,
            )
            await websocket.close(code=1008, reason="Too many connections")
            return False

        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(
            "[WS] User %s connected (%d total). Active users: %s",
            user_id, len(self.active_connections[user_id]),
            list(self.active_connections.keys()),
        )
        return True

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: int, message: dict):
        if user_id not in self.active_connections:
            return
        dead = []
        for conn in self.active_connections[user_id]:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn, user_id)

    async def broadcast_to_organization(self, organization_id: int, message: dict):
        """Broadcast to all connected users in an organization."""
        from app.db.models.user import User

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.id).filter(User.organization_id == organization_id)
            )
            org_user_ids = result.scalars().all()

        for uid in org_user_ids:
            await self.broadcast_to_user(uid, message)

    def broadcast_to_organization_sync(self, organization_id: int, message: dict):
        """Deprecated — use persisted notifications + Redis pub/sub instead."""
        logger.warning(
            "[WS-BROADCAST] Ignoring sync broadcast for org %s, type=%s. "
            "Use persisted notifications and Redis pub/sub instead.",
            organization_id, message.get("type"),
        )


notification_manager = NotificationConnectionManager()


# ── Helpers ───────────────────────────────────────────────────────────────


async def _get_latest_notification_id(user_id: int) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.max(Notification.id)).where(Notification.user_id == user_id)
        )
        latest = result.scalar_one_or_none()
        return int(latest or 0)


async def _get_new_notifications(user_id: int, after_id: int) -> list[Notification]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id, Notification.id > after_id)
            .order_by(Notification.id.asc())
        )
        return list(result.scalars().all())


def _notification_to_ws_message(notification: Notification) -> dict:
    payload = {
        "type": notification.type,
        "message": notification.message,
        "notification_id": notification.id,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "title": notification.title,
    }
    if notification.source_type == "document" and notification.source_id is not None:
        payload["document_id"] = notification.source_id
    return payload


async def get_token_user_id(token: str) -> int | None:
    try:
        from app.core.security import decode_access_token

        payload = decode_access_token(token)
        if payload is None:
            return None
        return payload.get("user_id")
    except Exception as e:
        logger.error("[Token Auth] Failed to decode token: %s", e)
        return None


# ── WebSocket endpoint ────────────────────────────────────────────────────

HEARTBEAT_INTERVAL = 30  # seconds


@router.websocket("/{token}")
async def websocket_notification_endpoint(websocket: WebSocket, token: str):
    user_id = await get_token_user_id(token)
    if not user_id:
        logger.warning("[WS] Rejecting connection — invalid token")
        await websocket.close(code=1008)
        return

    connected = await notification_manager.connect(websocket, user_id)
    if not connected:
        return  # limit exceeded, already closed

    # ── ONE-TIME catch-up from DB ─────────────────────────────────────
    last_seen_id = await _get_latest_notification_id(user_id)
    try:
        missed = await _get_new_notifications(user_id, 0)
        for n in missed[-50:]:  # cap catch-up to last 50
            await websocket.send_json(_notification_to_ws_message(n))
            last_seen_id = max(last_seen_id, n.id)
    except Exception as e:
        logger.warning("[WS] Catch-up failed for user %s: %s", user_id, e)

    # ── Subscribe to Redis pub/sub channel ────────────────────────────
    pubsub = None
    try:
        r = await get_redis()
        pubsub = r.pubsub()
        channel = f"notifications:{user_id}"
        await pubsub.subscribe(channel)
        logger.info("[WS] User %s subscribed to Redis channel %s", user_id, channel)

        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            # Check for Redis messages (non-blocking, 100ms timeout)
            try:
                redis_msg = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1),
                    timeout=0.5,
                )
                if redis_msg and redis_msg["type"] == "message":
                    data = json.loads(redis_msg["data"])
                    await websocket.send_json(data)
            except asyncio.TimeoutError:
                pass

            # Check for pings from client (non-blocking)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass

            # Heartbeat: send ping every HEARTBEAT_INTERVAL seconds
            now = asyncio.get_event_loop().time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                try:
                    await websocket.send_json({"type": "heartbeat"})
                    last_heartbeat = now
                except Exception:
                    break  # Connection dead

    except WebSocketDisconnect:
        logger.info("[WS] User %s disconnected normally", user_id)
    except Exception as e:
        logger.error("[WS] User %s connection error: %s", user_id, e)
        # Try to close gracefully
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        notification_manager.disconnect(websocket, user_id)
        if pubsub:
            try:
                await pubsub.unsubscribe(f"notifications:{user_id}")
                await pubsub.close()
            except Exception:
                pass
        logger.info(
            "[WS] User %s cleaned up. Active: %s",
            user_id, list(notification_manager.active_connections.keys()),
        )

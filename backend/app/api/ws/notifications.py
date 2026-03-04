import json
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_access_token
from app.core.config import settings
from app.db.session import AsyncSessionLocal

router = APIRouter()

class NotificationConnectionManager:
    def __init__(self):
        # Maps user_id to a list of active WebSocket connections
        self.active_connections: Dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error sending message to user {user_id}: {e}")

    async def broadcast_to_organization(self, organization_id: int, message: dict):
        from sqlalchemy import select
        from app.db.models.user import User
        from app.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User.id).filter(User.organization_id == organization_id))
            org_user_ids = result.scalars().all()
            
        for user_id in org_user_ids:
            await self.broadcast_to_user(user_id, message)

notification_manager = NotificationConnectionManager()

async def get_token_user_id(token: str) -> int:
    try:
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        if payload is None:
            print(f"WebSocket token decode returned None for token: {token[:10]}...")
            return None
        user_id = payload.get("user_id")
        print(f"WebSocket auth success for user_id: {user_id}")
        return user_id
    except Exception as e:
        print(f"WebSocket auth failed with exception: {e}")
        return None

@router.websocket("/{token}")
async def websocket_notification_endpoint(websocket: WebSocket, token: str):
    user_id = await get_token_user_id(token)
    if not user_id:
        await websocket.close(code=1008)
        return
        
    await notification_manager.connect(websocket, user_id)
    try:
        while True:
            # We don't expect messages from the client in this flow
            # but we need to keep the connection open and listen for disconnects
            data = await websocket.receive_text()
            # Handle ping/pong if necessary
    except WebSocketDisconnect:
        notification_manager.disconnect(websocket, user_id)

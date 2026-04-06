"""
Unit tests for the NotificationConnectionManager.
Tests connection limits, disconnect cleanup, and broadcast behavior.
These tests don't require a running database or Redis.
"""

import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ── Helpers ─────────────────────────────────────────────────────────────

class FakeWebSocket:
    """Minimal fake WebSocket for testing the connection manager."""

    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.sent_messages = []

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=None):
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def send_json(self, data):
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.sent_messages.append(data)


# ── Tests ───────────────────────────────────────────────────────────────

@pytest.fixture
def manager():
    """Create a fresh NotificationConnectionManager for each test."""
    from app.api.ws.notifications import NotificationConnectionManager
    return NotificationConnectionManager()


@pytest.mark.asyncio
async def test_connect_accepts_websocket(manager):
    ws = FakeWebSocket()
    with patch("app.api.ws.notifications.settings") as mock_settings:
        mock_settings.WS_MAX_CONNECTIONS_PER_USER = 5
        result = await manager.connect(ws, user_id=1)

    assert result is True
    assert ws.accepted is True
    assert 1 in manager.active_connections
    assert len(manager.active_connections[1]) == 1


@pytest.mark.asyncio
async def test_connect_rejects_when_limit_exceeded(manager):
    """Per-user connection limit should reject new connections."""
    with patch("app.api.ws.notifications.settings") as mock_settings:
        mock_settings.WS_MAX_CONNECTIONS_PER_USER = 2

        ws1, ws2, ws3 = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()

        assert await manager.connect(ws1, user_id=1) is True
        assert await manager.connect(ws2, user_id=1) is True
        # Third connection should be rejected
        assert await manager.connect(ws3, user_id=1) is False
        assert ws3.closed is True
        assert ws3.close_code == 1008
        assert len(manager.active_connections[1]) == 2


@pytest.mark.asyncio
async def test_connect_limit_per_user_not_global(manager):
    """Connection limit should be per-user, not global."""
    with patch("app.api.ws.notifications.settings") as mock_settings:
        mock_settings.WS_MAX_CONNECTIONS_PER_USER = 1

        ws1, ws2 = FakeWebSocket(), FakeWebSocket()

        assert await manager.connect(ws1, user_id=1) is True
        assert await manager.connect(ws2, user_id=2) is True
        assert len(manager.active_connections) == 2


@pytest.mark.asyncio
async def test_disconnect_removes_websocket(manager):
    with patch("app.api.ws.notifications.settings") as mock_settings:
        mock_settings.WS_MAX_CONNECTIONS_PER_USER = 5

        ws = FakeWebSocket()
        await manager.connect(ws, user_id=1)
        manager.disconnect(ws, user_id=1)

        assert 1 not in manager.active_connections


@pytest.mark.asyncio
async def test_disconnect_removes_only_specified_socket(manager):
    with patch("app.api.ws.notifications.settings") as mock_settings:
        mock_settings.WS_MAX_CONNECTIONS_PER_USER = 5

        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await manager.connect(ws1, user_id=1)
        await manager.connect(ws2, user_id=1)

        manager.disconnect(ws1, user_id=1)

        assert 1 in manager.active_connections
        assert len(manager.active_connections[1]) == 1
        assert manager.active_connections[1][0] is ws2


@pytest.mark.asyncio
async def test_broadcast_to_user_sends_to_all_connections(manager):
    with patch("app.api.ws.notifications.settings") as mock_settings:
        mock_settings.WS_MAX_CONNECTIONS_PER_USER = 5

        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await manager.connect(ws1, user_id=1)
        await manager.connect(ws2, user_id=1)

        await manager.broadcast_to_user(1, {"type": "test", "msg": "hello"})

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert ws1.sent_messages[0] == {"type": "test", "msg": "hello"}


@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections(manager):
    """If send_json raises, the dead connection should be removed."""
    with patch("app.api.ws.notifications.settings") as mock_settings:
        mock_settings.WS_MAX_CONNECTIONS_PER_USER = 5

        ws_good = FakeWebSocket()
        ws_dead = FakeWebSocket()
        ws_dead.closed = True  # Will raise on send_json

        await manager.connect(ws_good, user_id=1)
        await manager.connect(ws_dead, user_id=1)

        await manager.broadcast_to_user(1, {"type": "test"})

        # Dead connection should be removed
        assert len(manager.active_connections[1]) == 1
        assert manager.active_connections[1][0] is ws_good


@pytest.mark.asyncio
async def test_broadcast_to_user_no_connections(manager):
    """Broadcasting to a user with no connections should not raise."""
    await manager.broadcast_to_user(999, {"type": "test"})
    # Should not raise

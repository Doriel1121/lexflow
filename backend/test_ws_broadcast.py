"""
Test WebSocket connections and message broadcasting
Gets a real token by authenticating with the backend
"""

import asyncio
import websockets
import json
import logging
import sys
import httpx
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_pipeline():
    """Test WebSocket with real authentication"""
    
    print("\n" + "="*70)
    print("WEBSOCKET FULL PIPELINE TEST")
    print("="*70)
    
    # ─────────────────────────────────────────────────────────────
    # STEP 1: Authenticate and get a real token
    # ─────────────────────────────────────────────────────────────
    print("\n[STEP 1] Authenticating with backend...")
    
    # Test credentials (adjust these based on your test user)
    email = "admin@example.com"
    password = "admin123"
    
    token = None
    user_id = None
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                print(f"✅ Authentication successful!")
                print(f"   Token: {token[:40]}...")
                
                # Try to extract user_id from the response
                if "user_id" in data:
                    user_id = data["user_id"]
                    print(f"   User ID: {user_id}")
            else:
                print(f"❌ Authentication failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
    
    except Exception as e:
        print(f"❌ Could not authenticate: {e}")
        print(f"   Make sure:")
        print(f"   - Backend is running at http://localhost:8000")
        print(f"   - User {email} exists with password {password}")
        return False
    
    if not token:
        print("❌ No token received from authentication")
        return False
    
    # ─────────────────────────────────────────────────────────────
    # STEP 2: Connect to WebSocket with real token
    # ─────────────────────────────────────────────────────────────
    print("\n[STEP 2] Connecting to WebSocket with real token...")
    
    ws_url = f"ws://localhost:8000/api/v1/ws/notifications/{token}"
    print(f"   URL: {ws_url[:70]}...")
    
    messages_received = []
    ws_connected = False
    
    try:
        async with websockets.connect(ws_url, ping_interval=None) as websocket:
            ws_connected = True
            print("✅ WebSocket CONNECTED!\n")
            print("⏳ Listening for messages (20 second timeout)...\n")
            
            # Listen for up to 20 seconds
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 20:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=1)
                    data = json.loads(msg)
                    messages_received.append(data)
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"  📨 [{timestamp}] Message received!")
                    print(f"     Type: {data.get('type')}")
                    print(f"     Content: {json.dumps(data, indent=8)}\n")
                except asyncio.TimeoutError:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    print(f"  ⏱️  Waiting... ({int(elapsed)}s)                    ", end="\r")
                except json.JSONDecodeError as e:
                    print(f"  ⚠️  Received non-JSON message: {msg}\n")
    
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    # ─────────────────────────────────────────────────────────────
    # Results
    # ─────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    print(f"WebSocket Connection: ✅ CONNECTED")
    print(f"Messages Received: {len(messages_received)}")
    
    if ws_connected:
        print("\n✅ WebSocket is working! Messages can be received.")
    else:
        print("\n❌ WebSocket connection failed")
        return False
    
    if messages_received:
        print("\n✅ Messages are flowing through the WebSocket:")
        for i, msg in enumerate(messages_received, 1):
            msg_type = msg.get('type', 'UNKNOWN')
            print(f"   {i}. {msg_type}")
    else:
        print("\n⚠️  No messages were broadcast during the 20-second window")
        print("   This could mean:")
        print("   - No broadcasts are being sent from the backend")
        print("   - Broadcast system is not working")
        print("   - Try uploading a document in the UI while this test runs")
    
    return True

async def main():
    try:
        success = await test_websocket_pipeline()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

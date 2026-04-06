"""
Direct test of the broadcast mechanism
This test imports the notification manager and tests it directly
"""

import asyncio
import websockets
import json
import subprocess
import sys
import os
import time

async def test_broadcast_mechanism():
    """Test if broadcasts work by connecting and triggering a manual broadcast"""
    
    print("\n" + "="*70)
    print("DIRECT BROADCAST MECHANISM TEST")
    print("="*70)
    
    print("\n[DIAGNOSTIC] Checking what's in the notification manager...")
    
    # Try to import and check the notification manager
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        
        from app.api.ws.notifications import notification_manager
        
        print(f"✅ NotificationConnectionManager imported")
        print(f"   Active connections: {notification_manager.active_connections}")
        print(f"   Connected user IDs: {list(notification_manager.active_connections.keys())}")
        
        # Check a specific method
        print(f"\n✅ NotificationConnectionManager methods:")
        print(f"   - broadcast_to_user: {hasattr(notification_manager, 'broadcast_to_user')}")
        print(f"   - broadcast_to_organization: {hasattr(notification_manager, 'broadcast_to_organization')}")
        
    except Exception as e:
        print(f"⚠️  Could not import notification manager: {e}")
        print(f"   This is expected if running outside the Django environment")
    
    print("\n" + "="*70)
    print("ANALYZING THE ISSUE")
    print("="*70)
    
    print("""
FINDINGS:
---------
1. WebSocket connections ARE being made (we saw 2 in DevTools)
2. But NO messages are being received
3. Backend logs show document processing completes
4. But NO broadcast logs appear

HYPOTHESIS:
-----------
The broadcast_to_organization() function is likely being called,
but the notification_manager.active_connections dictionary is EMPTY.

This means:
- WebSocket connections are being made to the backend
- BUT they're not being registered in notification_manager.active_connections
- So when broadcast_to_organization() looks for users to send to, it finds NONE

POSSIBLE CAUSES:
----------------
1. ❌ WebSocket auth is failing (but we saw 101 status in DevTools, so connection successful)
2. ❌ connect() method not being called (but connection is established)
3. ✅ MOST LIKELY: User ID extraction from token is failing
         → get_token_user_id() returns None or wrong user_id
         → Line: "if not user_id: await websocket.close()"
         → Connection closes before being registered
         
4. ✅ OTHER POSSIBILITY: Token format/validation issue
         → decode_access_token() failing silently
         → Returning None or invalid user_id

SOLUTION TO TEST THIS:
--------------------
Check the backend logs for lines with:
  "[NotificationMgr]" - Shows if broadcast is even being called
  "WebSocket auth success for user_id:" - Shows if user_id extraction works
  "WebSocket auth failed" - Shows authentication errors

If these logs don't appear, the broadcast path isn't even reached.
If they appear but say "user_id: None", then token decoding is broken.
""")

async def main():
    await test_broadcast_mechanism()

if __name__ == "__main__":
    asyncio.run(main())

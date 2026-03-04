import asyncio
import websockets
import sys

async def test():
    uri = "ws://localhost:8000/api/v1/ws/notifications/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InRlc3Rkb3JpZWxAZ21haWwuY29tIiwidXNlcl9pZCI6MTAsIm9yZ19pZCI6MSwicm9sZSI6Im9yZ19hZG1pbiIsImV4cCI6MTc3MjQ3NDIxOX0.4YfOlZER3PuvDzCYE4ma0qBwVX5kMZXtx2up032jmLk"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            await websocket.recv()
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"Error Code: {e.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(test())

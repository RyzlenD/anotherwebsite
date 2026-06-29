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
    await asyncio.gather(*[viewer(message) for viewer in list(connected_viewers)], return_exceptions=True)

async def app(scope, receive, send):
    # --- 1. HANDLE HTTP ENTIRELY (Render Health Checks) ---
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
                # Enforce a 15-second maximum window for data or keep-alive pings
                try:
                    message = await asyncio.wait_for(receive(), timeout=15.0)
                except asyncio.TimeoutError:
                    logging.info(f"Connection timed out due to inactivity/silent disconnect.")
                    break # Break out to trigger the finally cleanup block
                
                if message['type'] == 'websocket.disconnect':
                    break
                
                if 'text' in message:
                    payload = json.loads(message['text'])
                    msg_type = payload.get("type")
                    
                    # Dashboard connection handshake
                    if msg_type == "register_viewer":
                        client_type = "viewer"
                        connected_viewers.add(send)
                        
                        await send({
                            'type': 'websocket.send',
                            'text': json.dumps({"type": "list", "data": list(live_targets.keys())})
                        })
                    
                    # Target connection handshake
                    elif msg_type == "register_target":
                        client_type = "target"
                        target_name = payload.get("COMPUTERNAME", "Unknown-Target")
                        live_targets[target_name] = send
                        
                        await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})
                    
                    # Relay screen streaming frame data
                    elif msg_type == "stream_frame" and client_type == "target":
                        frame_data = payload.get("frame")
                        await broadcast_to_viewers({
                            "type": "frame",
                            "user": target_name,
                            "frame": frame_data
                        })
                        await send({
                            'type': 'websocket.send',
                            'text': json.dumps({"status": "OK"})
                        })
                        
        except Exception as e:
            logging.error(f"Connection session encountered an error: {e}")
        finally:
            # Clean up records cleanly when either end terminates or times out
            if client_type == "viewer" and send in connected_viewers:
                connected_viewers.remove(send)
                logging.info("Viewer removed successfully.")
            elif client_type == "target" and target_name in live_targets:
                del live_targets[target_name]
                logging.info(f"Target '{target_name}' removed successfully.")
                # Update remaining viewers that target went offline
                await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
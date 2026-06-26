from flask import Flask, render_template, request, jsonify,redirect,url_for
import time
import threading
import os

app = Flask(__name__)
liveusers = {}

class LiveUser:
    def __init__(self, address):
        self.address = address
        self.lastinput = time.time()
        self.is_alive = True
        self.current_frame = None  
        self.pending_command = None  # <--- Stores "Shutdown" or "Restart" for the PC to grab
        
        print(f"Live created at {address}")
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def ping(self, frame_data=None):
        self.lastinput = time.time()
        if frame_data:
            self.current_frame = frame_data  
        print(f"[{self.address}] Ping received.")

    def _monitor_loop(self):
        while self.is_alive:
            if time.time() - self.lastinput > 10:
                print(f"[{self.address}] Inactive! Removing...")
                self.disconnect()
                break
            time.sleep(1)

    def disconnect(self):
        self.is_alive = False
        if str(self.address) in liveusers:
            del liveusers[str(self.address)]

def get_ip():
    # Render passes a comma-separated string of IPs in this header
    x_forwarded = request.headers.get("X-Forwarded-For")
    
    if x_forwarded:
        # The very first IP in the list is always the real client PC
        real_ip = x_forwarded.split(",")[0].strip()
        return real_ip
        
    # Fallback for when you test on your local network (192.168.x.x)
    return request.remote_addr

# --- SECURE KEY LOADING ---
KEY_FILE = "KEY.TXT"
if not os.path.exists(KEY_FILE):
    # Fallback default if you forget to make the file
    with open(KEY_FILE, "w") as f:
        f.write("ChangeMe123")

with open(KEY_FILE, "r") as f:
    SITE_SECRET_KEY = f.read().strip()


# --- ENFORCE KEY ON ALL PAGES ---
@app.before_request
def restrict_access():
    # Allow the client PC to POST stream frames to /live without cookies
    # Also don't block the login page or login submission route itself
    allowed_routes = ["login", "submit_key", "live"]
    if request.endpoint in allowed_routes:
        return

    # Check if user has the correct key saved in their browser cookies
    user_cookie = request.cookies.get("site_access_token")

    if user_cookie != SITE_SECRET_KEY:
        # Redirect them straight to the login screen
        return redirect(url_for("login"))


# --- ACCESS PATH ROUTES ---
@app.route("/login")
def login():
    # Simple, inline clean dark login form
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Access Required</title>
        <style>
            body { background: #0d0e15; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin:0; }
            .login-box { background: #1a1c2e; padding: 30px; border-radius: 8px; border: 1px solid #2e3152; text-align: center; box-shadow: 0 0 20px rgba(0,0,0,0.5); }
            input { background: #0d0e15; border: 1px solid #3b82f6; color: white; padding: 12px; border-radius: 4px; width: 200px; margin-bottom: 15px; font-size: 1rem; text-align: center; }
            button { background: #3b82f6; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer; font-weight: bold; width: 100%; font-size: 1rem;}
            button:hover { background: #2563eb; }
            p { color: #ef4444; font-size: 0.9rem; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>ENTER ACCESS KEY</h2>
            <form action="/login" method="POST">
                <input type="password" name="auth_key" placeholder="Key string..." required autocomplete="off"><br>
                <button type="submit">VALIDATE</button>
            </form>
            """ + (
        "<p>Invalid Key. Try again.</p>" if "error" in request.args else ""
    ) + """
        </div>
    </body>
    </html>
    """


@app.route("/login", methods=["POST"])
def submit_key():
    entered_key = request.form.get("auth_key", "").strip()

    if entered_key == SITE_SECRET_KEY:
        # Correct key! Redirect home and bake the key token into their cookies
        response = redirect(url_for("home"))
        # httponly=True protects the cookie from being stolen via malicious browser JS scripts
        response.set_cookie("site_access_token", SITE_SECRET_KEY, httponly=True)
        return response
    else:
        # Failed, bounce them back to login with error parameter
        return redirect(url_for("login", error=1))

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

# New Control Route: Receives button actions from your watch page
@app.route("/control/<address>", methods=["POST"])
def control(address):
    user = liveusers.get(address)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    data = request.get_json() or {}
    action = data.get("action") # Will be "Shutdown" or "Restart"
    
    print(f"[CONTROL] Stream: {address} | Action Clicked: {action}")
    
    # Store it inside this specific user's class object instance
    user.pending_command = action

    return jsonify({"status": "success", "message": f"Sent {action} to {address}"})

@app.route("/live", methods=["POST"])
def live():
    client_data = request.get_json() or {}
    thisip = str(get_ip())
    frame_data = client_data.get("frame") 
    if frame_data:
        print(f"--- SUCCESS: Received a frame string of length {len(frame_data)} from {thisip} ---")
    else:
        print(f"--- WARNING: Received data from {thisip} but 'frame' key was EMPTY or MISSING! ---")

    if thisip not in liveusers:
        liveusers[thisip] = LiveUser(address=thisip)
        
    user = liveusers[thisip]
    user.ping(frame_data=frame_data)

    # Return any pending commands back to the PC client inside the response!
    command_to_send = user.pending_command
    user.pending_command = None # Clear it so it doesn't repeat execution
    
    return jsonify({
        "status": "success",
        "server_message": "Frame updated",
        "command": command_to_send # Your PC script will look at this key!
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
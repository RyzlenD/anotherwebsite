from flask import Flask, render_template, request, jsonify
import time
import threading

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
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

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
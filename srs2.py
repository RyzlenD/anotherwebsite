import base64
import json
import os
import time
from io import BytesIO
from mss import mss
from PIL import Image
import websocket # pip install websocket-client

# Replace with your actual secure websocket URL on Render
RENDER_WS_URL = "wss://anotherwebsite-x1gv.onrender.com"

def start_streaming():
    print(f"Connecting to Render WebSocket Server at {RENDER_WS_URL}...")
    while True:
        try:
            ws = websocket.WebSocket()
            ws.connect(RENDER_WS_URL)

            # Handshake identity step
            comp_name = os.environ.get("COMPUTERNAME", "Unknown-PC")
            ws.send(json.dumps({"type": "register_target", "COMPUTERNAME": comp_name}))

            with mss() as sct:
                monitor = sct.monitors[1]
                while True:
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=5)
                    b64_frame = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    payload = {
                        "type": "stream_frame",
                        "frame": b64_frame
                    }
                    # Send payload
                    ws.send(json.dumps(payload))

                    # Read sync response frame verification back from Render
                    ws.recv()
                    
                    time.sleep(0.05) # Keep frame delivery pace balanced

        except Exception as e:
            print(f"Disconnected or error occurred: {e}. Retrying connection in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    start_streaming()
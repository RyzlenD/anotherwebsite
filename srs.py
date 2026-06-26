import base64
from io import BytesIO
import os
import requests
import time
from mss import mss
from PIL import Image

fps = 24
URL = "https://anotherwebsite-x1gv.onrender.com/live"
#URL = "http://192.168.1.184:5000/live"

print("Starting screen stream client...")

# Initialize the ultra-fast screen capturer
with mss() as sct:
    # Get primary monitor dimensions
    monitor = sct.monitors[1]

    while True:
        start_time = time.time()

        try:
            # 1. Capture the screen raw pixels
            screenshot = sct.grab(monitor)
            
            # 2. Convert raw pixels to a PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # Optional: Resize to lower bandwidth/improve performance if Render struggles
            # img = img.resize((1280, 720)) 

            # 3. Compress the image to JPEG in memory (BytesIO)
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=60) # Adjust quality (1-100) to balance clear vs fast
            
            # 4. Encode the binary JPEG image into a clean string format (Base64)
            b64_frame = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # 5. Pack everything up and send it
            payload = {
                "COMPUTERNAME": os.environ.get("COMPUTERNAME", "Unknown-PC"),
                "frame": b64_frame  # This matches the client_data.get("frame") on your Flask server
            }

            response = requests.post(URL, json=payload)

            if response.status_code == 200:
                server_reply = response.json()
                command = server_reply.get("command")
    
                if command == "Shutdown":
                    print("Received Shutdown directive from server!")
                    # Your local shutdown code goes here
                elif command == "Restart":
                    print("Received Restart directive from server!")
                print(f"Frame sent. Server response: {server_reply.get('server_message')}")
            else:
                print(f"Server returned an error code: {response.status_code}")

        except Exception as e:
            print(f"Streaming error: {e}")

        # 6. Dynamic FPS limiter (Accounts for time spent capturing/sending processing)
        elapsed_time = time.time() - start_time
        time_to_sleep = (1 / fps) - elapsed_time
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)
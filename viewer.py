import base64
import json
import threading
import time
import tkinter as tk
from tkinter import ttk
from io import BytesIO
from PIL import Image, ImageTk
import websocket  # Use 'pip install websocket-client' for synchronous client listening

available_targets = []
live_frames = {}

class ViewerDashboard(tk.Tk):
    def __init__(self, render_url):
        super().__init__()
        self.title("WebSocket Central Viewer")
        self.geometry("1000x650")
        self.render_url = render_url
        self.selected_target = None
        self.current_img_tk = None

        self._build_ui()
        # Fire up thread to listen to Render without freezing UI
        threading.Thread(target=self._network_listener, daemon=True).start()
        self._refresh_loop()

    def _build_ui(self):
        left_frame = ttk.LabelFrame(self, text=" Online Targets ", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.user_listbox = tk.Listbox(left_frame, width=35, font=("Consolas", 11))
        self.user_listbox.pack(fill=tk.BOTH, expand=True)
        self.user_listbox.bind("<<ListboxSelect>>", self._on_select)

        right_frame = ttk.Frame(self, padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.status_label = ttk.Label(right_frame, text="Select a target to view stream", font=("Arial", 12, "bold"))
        self.status_label.pack(anchor=tk.W, pady=(0, 10))

        self.canvas = tk.Canvas(right_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _network_listener(self):
        while True:
            try:
                # Open connection to the server
                ws = websocket.WebSocket()
                ws.connect(self.render_url)
                
                # Register as a viewer
                ws.send(json.dumps({"type": "register_viewer"}))
                
                while True:
                    result = ws.recv()
                    if not result: break
                    payload = json.loads(result)
                    
                    if payload.get("type") == "list":
                        global available_targets
                        available_targets = payload.get("data", [])
                    elif payload.get("type") == "frame":
                        live_frames[payload.get("user")] = payload.get("frame")
            except Exception as e:
                print(f"Server dropped connection: {e}. Reconnecting in 5s...")
                time.sleep(5)

    def _refresh_loop(self):
        self._update_listbox()
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

    def _on_select(self, event):
        selection = self.user_listbox.curselection()
        if selection:
            self.selected_target = self.user_listbox.get(selection[0])
            self.status_label.config(text=f"Streaming: {self.selected_target}")

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
        except Exception:
            pass

if __name__ == "__main__":
    # Swap out this dummy URL with your real Render wss:// link!
    RENDER_WS_URL = "wss://anotherwebsite-x1gv.onrender.com"
    app = ViewerDashboard(RENDER_WS_URL)
    app.mainloop()
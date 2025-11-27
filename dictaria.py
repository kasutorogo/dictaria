import os
import sys
import json
import tempfile
import threading
import queue
import time

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

import tkinter as tk
from tkinter import scrolledtext
from pynput import keyboard # For global hotkey

# --------------------
# CONFIGURATION & THEME
# --------------------

IS_MAC = sys.platform == "darwin"

# Hotkey settings
if IS_MAC:
    HOTKEY_COMBO = "<cmd>+<shift>+j"
    HOTKEY_LABEL = "Cmd + Shift + J"
    # Tkinter binding uses <Command>
    TK_HOTKEY = "<Command-Shift-J>"
else:
    HOTKEY_COMBO = "<ctrl>+<shift>+j"
    HOTKEY_LABEL = "Ctrl + Shift + J"
    # Tkinter binding uses <Control>
    TK_HOTKEY = "<Control-Shift-J>"

MODEL_SIZE = "medium"       # "small", "medium", "large-v3"
DEVICE = "cpu"              # Change to "cuda" if you have an NVIDIA GPU
COMPUTE_TYPE = "int8"       # "int8" is faster/lighter on CPU
SAMPLE_RATE = 16000
CONFIG_PATH = os.path.expanduser("~/.dictaria_config.json")
MAX_FAVORITES = 5

# --- IMPROVED THEME (Dark Pro / Slate) ---
THEME = {
    "root_bg": "#0f172a",      
    "topbar_bg": "#0f172a",     
    "topbar_fg": "#f1f5f9",     
    "card_bg": "#1e293b",      
    "border_color": "#334155",  
    "text_frame_bg": "#1e293b", 
    "text_box_bg": "#0D1116",  
    "text_fg": "#f1f5f9",      
    "record_idle_fill": "#ef4444",    
    "record_idle_outline": "#ef4444",
    "record_active_fill": "#fca5a5",    
    "record_active_outline": "#dc2626",
    "record_disabled_fill": "#334155",
    "record_disabled_outline": "#475569",
    "icon_fg": "#0D1116",
    "fav_active_bg": "#1e293b",
    "fav_active_fg": "#38bdf8", 
    "fav_inactive_bg": "#0f172a",
    "fav_inactive_fg": "#64748b",
}

# Language Definitions
LANG_DEFS = [
    ("es", "🇪🇸", "Español"), ("en", "🇬🇧", "English"),
    ("ja", "🇯🇵", "日本語"),   ("fr", "🇫🇷", "Français"),
    ("de", "🇩🇪", "Deutsch"), ("it", "🇮🇹", "Italiano"),
    ("pt", "🇵🇹", "Português"),("zh", "🇨🇳", "中文"),
    ("ru", "🇷🇺", "Русский"), ("ko", "🇰🇷", "한국어"),
]

# Messages
MSG_LOADING_MODEL = "[Initializing Dictaria... please wait]"
MSG_MODEL_READY = "[Dictaria Ready. Press {} to dictate]"
MSG_SELECT_LANG = "[Please select a language first]"
MSG_LISTENING = "[Listening...]"
MSG_PROCESSING = "[Transcribing...]"
MSG_NO_AUDIO = "[Audio too short or silent]"
MSG_ERROR = "[Error: {}]"
MSG_COPIED = "[Copied to clipboard]"


# --------------------
# AUDIO RECORDER CLASS
# --------------------
class AudioRecorder:
    """Handles low-level audio capture using sounddevice."""
    
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.queue = queue.Queue()
        self.stream = None
        self.is_recording = False

    def _callback(self, indata, frames, time, status):
        """Internal callback for sounddevice."""
        if status:
            print(f"Audio Status: {status}")
        self.queue.put(indata.copy())

    def start(self):
        """Starts the audio stream."""
        if self.is_recording:
            return
        self.is_recording = True
        
        # Clear previous data
        with self.queue.mutex:
            self.queue.queue.clear()
            
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._callback
            )
            self.stream.start()
            print("Audio stream started.")
        except Exception as e:
            print(f"Failed to start audio stream: {e}")
            self.is_recording = False

    def stop(self):
        """Stops the stream and returns the numpy audio array."""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            print("Audio stream stopped.")

        # Collect all chunks
        chunks = []
        while not self.queue.empty():
            chunks.append(self.queue.get())

        if not chunks:
            return None

        return np.concatenate(chunks, axis=0)


# --------------------
# MAIN APPLICATION
# --------------------
class DictariaApp:
    def __init__(self, root):
        self.root = root
        self.theme = THEME
        
        # Logic State
        self.recorder = AudioRecorder(sample_rate=SAMPLE_RATE)
        self.model = None
        self.model_loading = True
        
        self.favorites = []
        self.active_language = None
        self.show_help = True
        self.lang_vars = {} # For menu checkbuttons

        # UI Initialization
        self.load_config()
        self.build_ui()
        self.apply_config_to_ui()
        
        # Start Async Model Loading
        threading.Thread(target=self._load_model_thread, daemon=True).start()
        
        # Start the global hotkey listener separately
        self.global_hotkey_listener = start_global_hotkey_listener(self)

    def _get_emoji_font_name(self):
        """Determines the safest emoji font name based on the OS."""
        if os.name == "nt":
            # Windows
            return "Segoe UI Emoji"
        elif sys.platform == "darwin":
            # macOS
            return "Apple Color Emoji"
        else:
            # Linux (Uses 'Sans' as a safe generic fallback)
            return "Sans"

       # --- UI CONSTRUCTION ---

    def build_ui(self):
        self.root.geometry("560x650")
        self.root.minsize(500, 600)
        self.root.configure(bg=self.theme["root_bg"])
        self.root.title("Dictaria")

        # Global hotkey (works when the window has focus)
        self.root.bind_all(TK_HOTKEY, lambda e: self.toggle_record())

        # Top bar: only a centered "Languages" dropdown
        self.topbar = tk.Frame(self.root, bg=self.theme["topbar_bg"], height=40)
        self.topbar.pack(fill="x")

        # Use grid so we can center the Menubutton
        self.topbar.columnconfigure(0, weight=1)

        self.btn_lang = tk.Menubutton(
            self.topbar,
            text="Languages ▾",
            bg=self.theme["topbar_bg"],
            fg=self.theme["topbar_fg"],
            font=("Helvetica", 10),
            cursor="hand2",
            relief=tk.FLAT,
        )
        # Centered horizontally
        self.btn_lang.grid(row=0, column=0, pady=8)

        self.menu_lang = tk.Menu(self.btn_lang, tearoff=0)
        self.btn_lang.configure(menu=self.menu_lang)

        for code, flag, name in LANG_DEFS:
            var = tk.BooleanVar(value=False)
            self.lang_vars[code] = var
            self.menu_lang.add_checkbutton(
                label=f"{flag} {name}",
                variable=var,
                command=lambda c=code: self.toggle_favorite(c),
            )

        # Main card container
        self.card_frame = tk.Frame(
            self.root,
            bg=self.theme["card_bg"],
            highlightbackground=self.theme["border_color"],
            highlightthickness=1,
        )
        self.card_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # Favorites bar
        self.fav_container = tk.Frame(self.card_frame, bg=self.theme["card_bg"])
        self.fav_container.pack(pady=(15, 5))

        # Record button (canvas)
        self.canvas_btn = tk.Canvas(
            self.card_frame,
            width=80,
            height=80,
            bg=self.theme["card_bg"],
            highlightthickness=0,
        )
        self.canvas_btn.pack(pady=5)
        self.record_indicator = self.canvas_btn.create_oval(
            10,
            10,
            70,
            70,
            fill=self.theme["record_disabled_fill"],
            outline=self.theme["record_disabled_outline"],
            width=3,
        )
        self.canvas_btn.bind("<Button-1>", lambda e: self.toggle_record())

        # Text area
        self.text_frame = tk.Frame(self.card_frame, bg=self.theme["text_frame_bg"])
        self.text_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.text_box = scrolledtext.ScrolledText(
            self.text_frame,
            wrap=tk.WORD,
            font=("Helvetica", 12),
            bg=self.theme["text_box_bg"],
            fg=self.theme["text_fg"],
            insertbackground="white",  # caret color
            bd=0,
            padx=10,
            pady=10,
        )
        self.text_box.pack(fill="both", expand=True)

        # Try to darken the scrollbar (tkinter.scrolledtext exposes .vbar)
        try:
            self.text_box.vbar.config(
                bg=self.theme["card_bg"],              # scrollbar track
                troughcolor=self.theme["border_color"],
                activebackground=self.theme["record_idle_fill"],
                highlightthickness=0,
                bd=0,
            )
        except Exception:
            # On some platforms/themes these options may be ignored
            pass

        # Text tags (system vs error)
        # System messages: same red as the record button
        self.text_box.tag_config(
            "sys",
            foreground=self.theme["record_idle_fill"],  # #ef4444
            font=("Helvetica", 10, "italic"),
        )
        self.text_box.tag_config(
            "error",
            foreground="#ef4444",
            font=("Helvetica", 10, "bold"),
        )

        # Initial status message
        self.append_system(MSG_LOADING_MODEL)

    # --- LOGIC & THREADING ---

    def _load_model_thread(self):
        """Loads the Whisper model in background."""
        try:
            print(f"Loading Whisper Model ({MODEL_SIZE}) on {DEVICE}...")
            self.model = WhisperModel(
                MODEL_SIZE, 
                device=DEVICE, 
                compute_type=COMPUTE_TYPE
            )
            self.model_loading = False
            
            # Safe UI Update
            self.root.after(0, lambda: self.append_system(MSG_MODEL_READY.format(HOTKEY_LABEL)))
            self.root.after(0, self.update_record_button_style)
            print("Model loaded successfully.")
        except Exception as e:
            err = str(e)
            print(f"Model Load Error: {err}")
            self.root.after(0, lambda: self.append_system(MSG_ERROR.format(err), tag="error"))

    def toggle_record(self):
        """Main action: Start or Stop recording."""
        if self.model_loading:
            return # Ignore clicks while loading

        # --- FIX: Ensure a language is always selected if favorites exist ---
        if self.active_language is None:
            if self.favorites:
                self.active_language = self.favorites[0]
                self.refresh_favorites_bar()
            else:
                self.append_system(MSG_SELECT_LANG, tag="error")
                return
        # -------------------------------------------------------------------

        if not self.recorder.is_recording:
            # --- START RECORDING ---
            self.recorder.start()
            self.update_record_button_style()
            self.append_system(MSG_LISTENING)
        else:
            # --- STOP & TRANSCRIBE ---
            audio = self.recorder.stop()
            self.update_record_button_style()
            
            if audio is None:
                self.append_system(MSG_NO_AUDIO)
                return
            
            # Run transcription in a separate thread to keep UI responsive
            lang = self.active_language
            threading.Thread(
                target=self._transcribe_task, 
                args=(audio, lang), 
                daemon=True
            ).start()

    def _transcribe_task(self, audio, lang):
        """Background task for Whisper inference."""
        self.safe_append_system(MSG_PROCESSING)
        
        # Save audio to temp file (Whisper requirement)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_name = tmp.name
        
        try:
            sf.write(tmp_name, audio, SAMPLE_RATE)
            
            segments, info = self.model.transcribe(
                tmp_name, 
                language=lang,
                beam_size=5,
                condition_on_previous_text=False
            )
            
            full_text = " ".join([seg.text.strip() for seg in segments]).strip()
            
            if full_text:
                # Use the new function that appends and copies
                self.root.after(0, lambda t=full_text: self.safe_append_and_copy(t))
            else:
                self.safe_append_system(MSG_NO_AUDIO)
                
        except Exception as e:
            self.safe_append_system(MSG_ERROR.format(e), tag="error")
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    # --- UI HELPERS (Thread Safe) ---

    def safe_append_system(self, text, tag="sys"):
        self.root.after(0, lambda: self.append_system(text, tag))

    # --- NEW METHOD: Appends text and copies it to the clipboard ---
    def safe_append_and_copy(self, text):
        """Appends transcribed text to the box and copies it to the clipboard."""
        
        # 1. Append text to the text box
        self.text_box.insert(tk.END, text + "\n")
        self.text_box.see(tk.END)

        # 2. Copy to clipboard (requires being on the main thread)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.append_system(MSG_COPIED)
        except tk.TclError:
            # This can happen if the clipboard is locked or system fails
            self.append_system("[Warning: Failed to copy to clipboard]", tag="error")

    # --- END NEW METHOD ---

    # Kept for reference, but safe_append_and_copy is now used for transcription output
    def safe_append_text(self, text):
        self.root.after(0, lambda: self.text_box.insert(tk.END, text))
        self.root.after(0, lambda: self.text_box.see(tk.END))

    def append_system(self, text, tag="sys"):
        self.text_box.insert(tk.END, text + "\n", tag)
        self.text_box.see(tk.END)

    def update_record_button_style(self):
        """Updates the red button appearance based on state."""
        if self.model_loading or self.active_language is None:
            fill = self.theme["record_disabled_fill"]
            outline = self.theme["record_disabled_outline"]
        elif self.recorder.is_recording:
            fill = self.theme["record_active_fill"]
            outline = self.theme["record_active_outline"]
        else:
            fill = self.theme["record_idle_fill"]
            outline = self.theme["record_idle_outline"]

        self.canvas_btn.itemconfig(
            self.record_indicator, 
            fill=fill, 
            outline=outline
        )

    # --- SETTINGS & FAVORITES ---

    def toggle_favorite(self, code):
        """Handles menu clicks."""
        is_checked = self.lang_vars[code].get()
        
        if is_checked:
            if code not in self.favorites:
                if len(self.favorites) >= MAX_FAVORITES:
                    self.lang_vars[code].set(False) # Revert
                    self.append_system("[Favorites limit reached]", tag="error")
                    return
                self.favorites.append(code)
                # Auto-select if first one
                if self.active_language is None:
                    self.active_language = code
        else:
            if code in self.favorites:
                self.favorites.remove(code)
                if self.active_language == code:
                    self.active_language = self.favorites[0] if self.favorites else None
        
        self.refresh_favorites_bar()
        self.save_config()

    def set_active_language(self, code):
        self.active_language = code
        self.refresh_favorites_bar()
        self.save_config()

    def refresh_favorites_bar(self):
        # Clear existing widgets
        for widget in self.fav_container.winfo_children():
            widget.destroy()
            
        # Get the determined safe font name
        emoji_font_name = self._get_emoji_font_name()
        
        # Define sizes for the circle/canvas
        CIRCLE_SIZE = 40  # Diameter of the circle
        CANVAS_SIZE = 50  # Canvas width/height (padding added)
        
        # Define colors: Dark gray circle when inactive, Red circle when active.
        INACTIVE_COLOR = "#475569" # Slate 600 (Dark Gray)
        ACTIVE_COLOR = self.theme["record_idle_fill"]       # Red (#ef4444)
        CANVAS_BG = self.theme["card_bg"] # Background of the card frame (This ensures the flag container has no visible background)

        # Rebuild
        for code in self.favorites:
            # Find flag definition
            flag = next((f for c, f, n in LANG_DEFS if c == code), "?")
            is_active = (code == self.active_language)
            
            # Determine circle fill color based on state
            circle_fill = ACTIVE_COLOR if is_active else INACTIVE_COLOR
            
            # --- 1. Create Canvas (This acts as the container for the circle and flag) ---
            canvas = tk.Canvas(
                self.fav_container,
                width=CANVAS_SIZE,
                height=CANVAS_SIZE,
                bg=CANVAS_BG, # Set canvas background to match card_bg
                highlightthickness=0,
                cursor="hand2"
            )
            canvas.pack(side="left", padx=5)

            # --- 2. Draw the Circle (Oval) with the determined color ---
            # Coordinates are (x0, y0, x1, y1). Here 5px padding on each side for a 40px circle.
            canvas.create_oval(
                5, 5, 45, 45, 
                fill=circle_fill,
                outline="",
                width=0
            )
            
            # --- 3. Place the Flag Emoji in the center ---
            # Coordinates (x, y) = (CANVAS_SIZE / 2, CANVAS_SIZE / 2)
            canvas.create_text(
                CANVAS_SIZE // 2, 
                CANVAS_SIZE // 2, 
                text=flag,
                font=(emoji_font_name, 16), 
                fill="white"
            )
            
            # --- 4. Bind click event to the canvas ---
            canvas.bind("<Button-1>", lambda e, c=code: self.set_active_language(c))
            
        self.update_record_button_style()

    def load_config(self):
        """Loads config and ensures the first favorite is selected if available."""
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                self.favorites = data.get("favorites", [])
                
                # --- FIX: Ensure the active language is always the first favorite ---
                if self.favorites:
                    self.active_language = self.favorites[0]
                else:
                    self.active_language = None
        except Exception:
            pass

    def apply_config_to_ui(self):
        # Sync menu variables
        for code, var in self.lang_vars.items():
            var.set(code in self.favorites)
        self.refresh_favorites_bar()

    def save_config(self):
        data = {
            "favorites": self.favorites,
            "active": self.active_language # Save active state
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Config Save Error: {e}")

# --------------------
# GLOBAL HOTKEY SETUP (pynput)
# --------------------
def start_global_hotkey_listener(app_instance):
    """
    Starts the global hotkey listener in a daemon thread using pynput.
    This runs even if the app is in the background.
    """
    def on_activate():
        print(f"Global hotkey {HOTKEY_LABEL} pressed.")
        # CRITICAL: Schedule the action on the main GUI thread.
        app_instance.root.after(0, app_instance.toggle_record)

    try:
        listener = keyboard.GlobalHotKeys({
            HOTKEY_COMBO: on_activate
        })
        listener.daemon = True
        listener.start()
        print("Global hotkey listener started (pynput).")
        return listener
    except Exception as e:
        print(f"Error starting pynput global hotkey listener: {e}")
        print("Falling back to in-app hotkey only.")
        return None

# --------------------
# ENTRY POINT
# --------------------
def main():
    root = tk.Tk()
    
    # Attempt to set window icon if file exists
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            img = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, img)
    except Exception:
        pass

    app = DictariaApp(root)
    
    root.mainloop()

if __name__ == "__main__":
    main()

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
from pynput import keyboard 

# --------------------
# CONFIGURATION & THEME
# --------------------

IS_MAC = sys.platform == "darwin"

# Hotkey settings (MODIFIED TO F9 TO AVOID F12 CONFLICTS)
if IS_MAC:
    HOTKEY_COMBO = "<cmd>+<alt>+f9"
    HOTKEY_LABEL = "Cmd + Option + F9"
    TK_HOTKEY = "<Command-Option-F9>"
else:
    HOTKEY_COMBO = "<ctrl>+<alt>+f9"
    HOTKEY_LABEL = "Ctrl + Alt + F9"
    TK_HOTKEY = "<Control-Alt-F9>"

MODEL_SIZE = "medium"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
SAMPLE_RATE = 16000
CONFIG_PATH = os.path.expanduser("~/.dictaria_config.json")
MAX_FAVORITES = 3 # Kept for consistency, but favorites UI is removed

# --- THEME (Dark Pro / Slate) ---
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
    "pin_active_fg": "#38bdf8", 
    "pin_inactive_fg": "#64748b", 
}

# Language Definitions (Simplified for OptionMenu)
LANG_DEFS = {
    "es": {"flag": "🇪🇸", "name": "Spanish"}, 
    "en": {"flag": "🇬🇧", "name": "English"},
    "ja": {"flag": "🇯🇵", "name": "Japanese"},
    "fr": {"flag": "🇫🇷", "name": "French"},
    "de": {"flag": "🇩🇪", "name": "German"},
    "it": {"flag": "🇮🇹", "name": "Italian"},
    "pt": {"flag": "🇵🇹", "name": "Portuguese"},
    "zh": {"flag": "🇨🇳", "name": "Chinese"},
    "ru": {"flag": "🇷🇺", "name": "Russian"},
    "ko": {"flag": "🇰🇷", "name": "Korean"},
}
LANG_CODES = list(LANG_DEFS.keys())
# Menu Options are the full English names (e.g., "Spanish 🇪🇸")
LANG_OPTIONS = [f"{v['name']} {v['flag']}" for v in LANG_DEFS.values()]


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
# AUDIO RECORDER CLASS (No changes)
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
        self.is_pinned = False 
        
        # Favorites list removed.
        self.active_language = None 
        
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

    # --- UI CONSTRUCTION (ULTRA-MINIMALIST) ---

    def build_ui(self):
        # 1. WINDOW SIZE REDUCED AND ADJUSTED FOR NEW LAYOUT
        self.root.geometry("300x400") # Smaller window
        self.root.minsize(280, 350)
        self.root.configure(bg=self.theme["root_bg"])
        self.root.title("Dictaria")

        self.root.bind_all(TK_HOTKEY, lambda e: self.toggle_record())

        # --- CONTROLS CONTAINER (Replaces Topbar and upper Card_frame) ---
        # This Frame will contain the pin, the dropdown, and the record button.
        self.controls_frame = tk.Frame(self.root, bg=self.theme["root_bg"])
        self.controls_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # We use Grid to organize the 3 key elements horizontally: Pin | Dropdown | Spacer
        self.controls_frame.columnconfigure(0, weight=0) # Pin
        self.controls_frame.columnconfigure(1, weight=1) # Dropdown (Expands)
        self.controls_frame.columnconfigure(2, weight=0) # Spacer 

        # 1. PIN BUTTON (Left)
        self.btn_pin = tk.Canvas(
            self.controls_frame,
            width=20,
            height=20,
            bg=self.theme["root_bg"],
            highlightthickness=0,
            cursor="hand2"
        )
        self.btn_pin.grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.pin_text = self.btn_pin.create_text(
            10, 10, 
            text="📌", 
            font=("Helvetica", 12),
            fill=self.theme["pin_inactive_fg"]
        )
        self.btn_pin.bind("<Button-1>", lambda e: self.toggle_pin())
        
        # 2. LANGUAGE DROPDOWN (Center)
        # Variable to store the selected option (will be the full name + flag)
        self.lang_var = tk.StringVar(self.controls_frame)
        self.lang_var.set(LANG_OPTIONS[0]) # Initial value
        
        # When the variable value changes, set_active_language_from_menu is called
        self.lang_var.trace_add("write", self.set_active_language_from_menu)

        self.option_menu_lang = tk.OptionMenu(
            self.controls_frame,
            self.lang_var,
            *LANG_OPTIONS
        )
        self.option_menu_lang.config(
            bg=self.theme["topbar_bg"], 
            fg=self.theme["topbar_fg"],
            activebackground=self.theme["border_color"],
            activeforeground=self.theme["topbar_fg"],
            bd=0, relief=tk.FLAT, font=("Helvetica", 10),
        )
        # The internal menu widget (the dropdown list) must also be themed
        menu = self.root.winfo_children()[-1]
        if isinstance(menu, tk.Menu):
            menu.config(bg=self.theme["topbar_bg"], fg=self.theme["topbar_fg"], bd=0)
            
        self.option_menu_lang.grid(row=0, column=1, sticky="ew", pady=5, padx=5) 
        
        # 3. Spacer (column 2) to balance the grid if necessary
        tk.Label(self.controls_frame, bg=self.theme["root_bg"], width=3).grid(row=0, column=2, sticky="e")

        # --- BOTTOM CONTROLS: Record Button ---
        self.controls_bottom_frame = tk.Frame(self.root, bg=self.theme["root_bg"])
        self.controls_bottom_frame.pack(padx=10, pady=(0, 10))

        # Record button (canvas) (60x60)
        self.canvas_btn = tk.Canvas(
            self.controls_bottom_frame,
            width=60,
            height=60,
            bg=self.theme["root_bg"],
            highlightthickness=0,
        )
        self.canvas_btn.pack(pady=(0, 5))
        self.record_indicator = self.canvas_btn.create_oval(
            5, 5, 55, 55,
            fill=self.theme["record_disabled_fill"],
            outline=self.theme["record_disabled_outline"],
            width=3,
        )
        self.canvas_btn.bind("<Button-1>", lambda e: self.toggle_record())

        # --- TEXT AREA (Now occupies almost all remaining space) ---
        self.text_frame = tk.Frame(self.root, bg=self.theme["text_frame_bg"])
        # We use fill/expand so it stretches maximally
        self.text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.text_box = scrolledtext.ScrolledText(
            self.text_frame,
            wrap=tk.WORD,
            font=("Helvetica", 11),
            bg=self.theme["text_box_bg"],
            fg=self.theme["text_fg"],
            insertbackground="white", 
            bd=0,
            padx=10,
            pady=10,
        )
        self.text_box.pack(fill="both", expand=True)

        try:
            self.text_box.vbar.config(
                bg=self.theme["root_bg"],              
                troughcolor=self.theme["border_color"],
                activebackground=self.theme["record_idle_fill"],
                highlightthickness=0,
                bd=0,
            )
        except Exception:
            pass

        # Text tags (system vs error)
        self.text_box.tag_config(
            "sys",
            foreground=self.theme["record_idle_fill"], 
            font=("Helvetica", 10, "italic"),
        )
        self.text_box.tag_config(
            "error",
            foreground="#ef4444",
            font=("Helvetica", 10, "bold"),
        )

        self.append_system(MSG_LOADING_MODEL)


    # --- LANGUAGE AND CONFIGURATION LOGIC (UPDATED) ---

    def _get_lang_code_from_option(self, option_text):
        """Converts 'Spanish 🇪🇸' back to 'es'."""
        for code, defs in LANG_DEFS.items():
            if option_text.startswith(defs['name']):
                return code
        return LANG_CODES[0] # Fallback to the first language

    def set_active_language_from_menu(self, *args):
        """Automatically called when the OptionMenu changes."""
        selected_option = self.lang_var.get()
        new_code = self._get_lang_code_from_option(selected_option)
        
        # Prevent infinite loops if the trace is triggered on load
        if new_code != self.active_language:
            self.active_language = new_code
            self.append_system(f"[Language set to: {LANG_DEFS[new_code]['name']}]")
            self.update_record_button_style()
            self.save_config()


    # --- REMOVED: refresh_favorites_bar (no longer exists) ---


    def load_config(self):
        """Loads config and sets the active language."""
        initial_lang_code = LANG_CODES[0] # Default to the first defined language
        
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    
                    # Load the active language (if valid)
                    last_active = data.get("active", initial_lang_code)
                    if last_active in LANG_CODES:
                        initial_lang_code = last_active
                        
            except Exception:
                pass
                
        self.active_language = initial_lang_code


    def apply_config_to_ui(self):
        """Applies the active language to the UI dropdown."""
        
        if self.active_language:
            # Find the full menu option matching the saved code
            active_option = f"{LANG_DEFS[self.active_language]['name']} {LANG_DEFS[self.active_language]['flag']}"
            
            if active_option in LANG_OPTIONS:
                # Set the OptionMenu variable value
                self.lang_var.set(active_option)
            else:
                # Fallback to the first language if the saved code is invalid
                self.active_language = LANG_CODES[0]
                self.lang_var.set(LANG_OPTIONS[0])
                
        self.update_record_button_style()


    def save_config(self):
        """Saves only the active language."""
        data = {
            "active": self.active_language 
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Config Save Error: {e}")

    # --- APP LOGIC (Minimum adjustments) ---

    def toggle_pin(self):
        """Toggles the 'always on top' state of the window."""
        self.is_pinned = not self.is_pinned
        self.root.attributes('-topmost', self.is_pinned)
        
        color = self.theme["pin_active_fg"] if self.is_pinned else self.theme["pin_inactive_fg"]
        self.btn_pin.itemconfig(self.pin_text, fill=color)
        
        pin_state = "ON" if self.is_pinned else "OFF"
        self.append_system(f"[Pin Mode {pin_state}]")

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
            return 
            
        if self.active_language is None:
            self.append_system(MSG_SELECT_LANG, tag="error")
            return

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
                # Appends text and copies it to the clipboard
                self.root.after(0, lambda t=full_text: self.safe_append_and_copy(t))
            else:
                self.safe_append_system(MSG_NO_AUDIO)
                
        except Exception as e:
            self.safe_append_system(MSG_ERROR.format(e), tag="error")
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    # --- UI HELPERS (Thread Safe) (No changes) ---

    def safe_append_system(self, text, tag="sys"):
        self.root.after(0, lambda: self.append_system(text, tag))

    def safe_append_and_copy(self, text):
        """Appends transcribed text to the box and copies it to the clipboard."""
        self.text_box.insert(tk.END, text + "\n")
        self.text_box.see(tk.END)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.append_system(MSG_COPIED)
        except tk.TclError:
            self.append_system("[Warning: Failed to copy to clipboard]", tag="error")

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


# --------------------
# GLOBAL HOTKEY SETUP (pynput)
# --------------------
def start_global_hotkey_listener(app_instance):
    """
    Starts the global hotkey listener in a daemon thread using pynput.
    This runs even if the app is in the background.
    
    NOTE: On macOS/Linux/Windows, this requires OS-level permissions (e.g., 
    Accessibility/Input Monitoring). If this fails, the hotkey will only 
    work when the Dictaria window is focused.
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
        print(f"Global hotkey listener started (pynput). Hotkey: {HOTKEY_LABEL}")
        return listener
    except Exception as e:
        # The specific error 'f12' indicates a key is intercepted by the OS/Shell.
        print(f"Error starting pynput global hotkey listener: {e}")
        print("ACTION REQUIRED: The global hotkey is likely failing due to missing OS permissions or a conflicting system shortcut. Please check your OS settings.")
        print("Falling back to in-app hotkey only (only works when the window is focused).")
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

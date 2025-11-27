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

# --- Platform detection ---
IS_MAC = sys.platform == "darwin"

# --- Conditional pynput import (only non-mac) ---
if not IS_MAC:
    try:
        from pynput import keyboard
        print("[System] pynput imported successfully for non-Mac systems.")
    except ImportError:
        print("[System] Warning: pynput not installed. Global hotkey will not work on this system.")
        keyboard = None
else:
    keyboard = None

# --------------------
# CONFIGURATION & THEME
# --------------------

# Hotkey settings
SIGNAL_FILE = "/tmp/dictaria_signal_f9.txt"  # Used only on macOS with Hammerspoon

if IS_MAC:
    HOTKEY_LABEL = "Cmd + Option + F9 (via Hammerspoon)"
    TK_HOTKEY = "<Command-Option-F9>"  # In-app hotkey fallback when window is focused
    GLOBAL_HOTKEY_COMBO = None  # Not used on macOS (Hammerspoon handles it)
else:
    # Windows/Linux (via pynput)
    HOTKEY_LABEL = "Ctrl + Alt + F9 (via pynput)"
    TK_HOTKEY = "<Control-Alt-F9>"
    # pynput GlobalHotKeys combo syntax
    GLOBAL_HOTKEY_COMBO = "<ctrl>+<alt>+<f9>"

MODEL_SIZE = "medium"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
SAMPLE_RATE = 16000
CONFIG_PATH = os.path.expanduser("~/.dictaria_config.json")

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
    "scrollbar_trough": "#000000",  # pista negra para scrollbar
    "scrollbar_thumb": "#334155",   # pulgar gris oscuro para scrollbar
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
LANG_OPTIONS = [f"{v['name']} {v['flag']}" for v in LANG_DEFS.values()]

# Messages
MSG_LOADING_MODEL = "[Initializing Dictaria... please wait]"
MSG_MODEL_READY = f"[Dictaria Ready. Press {HOTKEY_LABEL} to dictate]"
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

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio Status: {status}")
        self.queue.put(indata.copy())

    def start(self):
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
                callback=self._callback,
            )
            self.stream.start()
            print("Audio stream started.")
        except Exception as e:
            print(f"Failed to start audio stream: {e}")
            self.is_recording = False

    def stop(self):
        if not self.is_recording:
            return None

        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            print("Audio stream stopped.")

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

        # --- Collapse State and Heights ---
        self.is_collapsed = False
        self.INITIAL_SIZE = "300x400"
        self.MIN_HEIGHT = 160 
        self.ORIGINAL_WIDTH = 0
        self.ORIGINAL_HEIGHT = 0
        
        self.recorder = AudioRecorder(sample_rate=SAMPLE_RATE)
        self.model = None
        self.model_loading = True
        self.is_pinned = False
        self.active_language = None

        self.keyboard_listener = None  # pynput listener (non-mac only)

        self.load_config()
        self.build_ui()
        self.apply_config_to_ui()

        threading.Thread(target=self._load_model_thread, daemon=True).start()

        # Hotkey backends
        if IS_MAC:
            start_hammerspoon_listener(self)
        else:
            self.start_pynput_hotkey_listener()

    # --- pynput global hotkey for Windows/Linux ---
    def start_pynput_hotkey_listener(self):
        """Starts a pynput GlobalHotKeys listener on non-mac systems."""
        if not keyboard or not GLOBAL_HOTKEY_COMBO:
            print("[System] Global hotkey disabled (pynput missing or combo not set).")
            print("[System] You can still use the in-window hotkey and the red button.")
            return

        def on_activate():
            print("[System] pynput hotkey detected. Toggling record.")
            self.root.after(0, self.toggle_record)

        try:
            # GlobalHotKeys expects a dict {combo: callback}
            self.keyboard_listener = keyboard.GlobalHotKeys({
                GLOBAL_HOTKEY_COMBO: on_activate
            })
            self.keyboard_listener.start()
            print(f"[System] pynput GlobalHotKeys started for combo: {GLOBAL_HOTKEY_COMBO}")
        except Exception as e:
            print(f"[System] Error starting pynput listener: {e}")
            self.keyboard_listener = None

    # --- UI CONSTRUCTION (ULTRA-MINIMALIST) ---
    def build_ui(self):
        self.root.geometry(self.INITIAL_SIZE)
        self.root.minsize(280, self.MIN_HEIGHT) 
        self.root.configure(bg=self.theme["root_bg"])
        self.root.title("Dictaria")

        # In-window hotkey
        self.root.bind_all(TK_HOTKEY, lambda e: self.toggle_record())

        # Controls frame (Top bar: Pin | Lang | Collapse)
        self.controls_frame = tk.Frame(self.root, bg=self.theme["root_bg"])
        self.controls_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.controls_frame.columnconfigure(0, weight=0) # Pin
        self.controls_frame.columnconfigure(1, weight=1) # Language
        self.controls_frame.columnconfigure(3, weight=0) # Collapse

        # Pin button
        self.btn_pin = tk.Canvas(
            self.controls_frame,
            width=20,
            height=20,
            bg=self.theme["root_bg"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.btn_pin.grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.pin_text = self.btn_pin.create_text(
            10,
            10,
            text="📌",
            font=("Helvetica", 12),
            fill=self.theme["pin_inactive_fg"],
        )
        self.btn_pin.bind("<Button-1>", lambda e: self.toggle_pin())

        # Language dropdown
        self.lang_var = tk.StringVar(self.controls_frame)
        self.lang_var.set(LANG_OPTIONS[0])
        self.lang_var.trace_add("write", self.set_active_language_from_menu)

        self.option_menu_lang = tk.OptionMenu(
            self.controls_frame,
            self.lang_var,
            *LANG_OPTIONS,
        )
        self.option_menu_lang.config(
            bg=self.theme["topbar_bg"],
            fg=self.theme["topbar_fg"],
            activebackground=self.theme["border_color"],
            activeforeground=self.theme["topbar_fg"],
            bd=0,
            relief=tk.FLAT,
            font=("Helvetica", 10),
        )

        # Theme the internal dropdown menu in a robust way
        menu = self.option_menu_lang["menu"]
        menu.config(
            bg=self.theme["topbar_bg"],
            fg=self.theme["topbar_fg"],
            bd=0,
            activebackground=self.theme["border_color"],
            activeforeground=self.theme["topbar_fg"],
        )

        self.option_menu_lang.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # --- Collapse Button ---
        self.btn_collapse = tk.Canvas(
            self.controls_frame,
            width=20,
            height=20,
            bg=self.theme["root_bg"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.btn_collapse.grid(row=0, column=3, sticky="e", padx=(5, 0)) 
        
        self.collapse_text = self.btn_collapse.create_text(
            10,
            10,
            text="⬇️",  # Initial state: Down arrow (can collapse)
            font=("Helvetica", 12),
            fill=self.theme["pin_inactive_fg"],
        )
        self.btn_collapse.bind("<Button-1>", lambda e: self.toggle_collapse())
        # ---------------------------

        # Record button frame
        self.controls_bottom_frame = tk.Frame(self.root, bg=self.theme["root_bg"])
        self.controls_bottom_frame.pack(padx=10, pady=(0, 10)) 

        self.canvas_btn = tk.Canvas(
            self.controls_bottom_frame,
            width=60,
            height=60,
            bg=self.theme["root_bg"],
            highlightthickness=0,
        )
        self.canvas_btn.pack(pady=(0, 5))
        self.record_indicator = self.canvas_btn.create_oval(
            5,
            5,
            55,
            55,
            fill=self.theme["record_disabled_fill"],
            outline=self.theme["record_disabled_outline"],
            width=3,
        )
        self.canvas_btn.bind("<Button-1>", lambda e: self.toggle_record())

        # Text area
        self.text_frame = tk.Frame(self.root, bg=self.theme["text_frame_bg"])
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
            # Scrollbar tema oscuro
            self.text_box.vbar.config(
                bg=self.theme["scrollbar_thumb"],
                troughcolor=self.theme["scrollbar_trough"],
                activebackground=self.theme["border_color"],
                highlightthickness=0,
                bd=0,
            )
        except Exception:
            pass

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
        
        # Store original window size
        self.root.update_idletasks()
        self.ORIGINAL_WIDTH = self.root.winfo_width()
        self.ORIGINAL_HEIGHT = self.root.winfo_height()

    # --- NEW COLLAPSE LOGIC ---
    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed

        if self.is_collapsed:
            # 1. Hide the text frame (the bulk of the UI)
            self.text_frame.pack_forget()
            
            # 2. Set window size to minimum height
            self.root.geometry(f"{self.ORIGINAL_WIDTH}x{self.MIN_HEIGHT}")
            self.root.minsize(self.ORIGINAL_WIDTH, self.MIN_HEIGHT)

            # 3. Change collapse icon
            self.btn_collapse.itemconfig(self.collapse_text, text="⬆️")
            self.append_system("[View Collapsed]")
        else:
            # 1. Restore window size
            self.root.geometry(f"{self.ORIGINAL_WIDTH}x{self.ORIGINAL_HEIGHT}")
            self.root.minsize(280, 350) # Restore general minsize

            # 2. Show the text frame again
            self.text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            # 3. Change collapse icon
            self.btn_collapse.itemconfig(self.collapse_text, text="⬇️")
            self.append_system("[View Restored]")


    # --- LANGUAGE / CONFIG ---
    def _get_lang_code_from_option(self, option_text):
        for code, defs in LANG_DEFS.items():
            if option_text.startswith(defs["name"]):
                return code
        return LANG_CODES[0]

    def set_active_language_from_menu(self, *args):
        selected_option = self.lang_var.get()
        new_code = self._get_lang_code_from_option(selected_option)

        if new_code != self.active_language:
            self.active_language = new_code
            self.append_system(f"[Language set to: {LANG_DEFS[new_code]['name']}]")
            self.update_record_button_style()
            self.save_config()

    def load_config(self):
        initial_lang_code = LANG_CODES[0]
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    last_active = data.get("active", initial_lang_code)
                    if last_active in LANG_CODES:
                        initial_lang_code = last_active
            except Exception:
                pass
        self.active_language = initial_lang_code

    def apply_config_to_ui(self):
        if self.active_language:
            active_option = f"{LANG_DEFS[self.active_language]['name']} {LANG_DEFS[self.active_language]['flag']}"
            if active_option in LANG_OPTIONS:
                self.lang_var.set(active_option)
            else:
                self.active_language = LANG_CODES[0]
                self.lang_var.set(LANG_OPTIONS[0])
        self.update_record_button_style()

    def save_config(self):
        data = {"active": self.active_language}
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Config Save Error: {e}")

    # --- APP LOGIC ---
    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.root.attributes("-topmost", self.is_pinned)
        color = (
            self.theme["pin_active_fg"]
            if self.is_pinned
            else self.theme["pin_inactive_fg"]
        )
        self.btn_pin.itemconfig(self.pin_text, fill=color)
        pin_state = "ON" if self.is_pinned else "OFF"
        self.append_system(f"[Pin Mode {pin_state}]")

    def _load_model_thread(self):
        try:
            print(f"Loading Whisper Model ({MODEL_SIZE}) on {DEVICE}...")
            self.model = WhisperModel(
                MODEL_SIZE,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
            )
            self.model_loading = False
            self.root.after(0, lambda: self.append_system(MSG_MODEL_READY))
            self.root.after(0, self.update_record_button_style)
            print("Model loaded successfully.")
        except Exception as e:
            err = str(e)
            print(f"Model Load Error: {err}")
            self.root.after(
                0, lambda: self.append_system(MSG_ERROR.format(err), tag="error")
            )

    def toggle_record(self):
        if self.model_loading:
            return

        if self.active_language is None:
            self.append_system(MSG_SELECT_LANG, tag="error")
            return

        if not self.recorder.is_recording:
            self.recorder.start()
            self.update_record_button_style()
            self.append_system(MSG_LISTENING)
        else:
            audio = self.recorder.stop()
            self.update_record_button_style()

            if audio is None:
                self.append_system(MSG_NO_AUDIO)
                return

            lang = self.active_language
            threading.Thread(
                target=self._transcribe_task,
                args=(audio, lang),
                daemon=True,
            ).start()

    def _transcribe_task(self, audio, lang):
        self.safe_append_system(MSG_PROCESSING)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_name = tmp.name

        try:
            sf.write(tmp_name, audio, SAMPLE_RATE)
            segments, info = self.model.transcribe(
                tmp_name,
                language=lang,
                beam_size=5,
                condition_on_previous_text=False,
            )
            full_text = " ".join([seg.text.strip() for seg in segments]).strip()

            if full_text:
                self.root.after(0, lambda t=full_text: self.safe_append_and_copy(t))
            else:
                self.safe_append_system(MSG_NO_AUDIO)
        except Exception as e:
            self.safe_append_system(MSG_ERROR.format(e), tag="error")
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    # --- UI HELPERS ---
    def safe_append_system(self, text, tag="sys"):
        self.root.after(0, lambda: self.append_system(text, tag))

    def safe_append_and_copy(self, text):
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
            outline=outline,
        )


# --------------------
# HAMMERSPOON LISTENER (macOS ONLY)
# --------------------
def start_hammerspoon_listener(app_instance):
    if os.path.exists(SIGNAL_FILE):
        try:
            os.remove(SIGNAL_FILE)
        except OSError as e:
            print(f"[System] Warning: Could not remove old signal file: {e}")

    def check_signal():
        if os.path.exists(SIGNAL_FILE):
            try:
                os.remove(SIGNAL_FILE)
            except OSError as e:
                print(f"[System] Error removing signal file: {e}")
            print("[System] Signal file found. Toggling record.")
            app_instance.root.after(0, app_instance.toggle_record)

        app_instance.root.after(100, check_signal)

    print(f"Hammerspoon Listener started (File Polling) on: {SIGNAL_FILE}")
    check_signal()


# --------------------
# ENTRY POINT
# --------------------
def main():
    root = tk.Tk()

    try:
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            img = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, img)
    except Exception:
        pass

    app = DictariaApp(root)

    def on_closing():
        if app.keyboard_listener:
            try:
                app.keyboard_listener.stop()
                print("pynput listener stopped.")
            except Exception:
                pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

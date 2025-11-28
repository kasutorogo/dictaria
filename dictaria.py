import os
import sys
import json
import tempfile
import threading
import queue
import time
import concurrent.futures
from typing import NamedTuple, List, Dict

import numpy as np
import sounddevice as sd
import soundfile as sf
# Conditional import for pynput is handled in main()

from faster_whisper import WhisperModel

import tkinter as tk
from tkinter import scrolledtext


# Hotkey settings
SIGNAL_FILE = "/tmp/dictaria_signal_f9.txt" # Used only on macOS with Hammerspoon
IS_MAC = sys.platform == "darwin"

if IS_MAC:
    HOTKEY_LABEL = "Cmd + Option + F9"
    TK_HOTKEY = "<Command-Option-F9>" # In-window hotkey
    GLOBAL_HOTKEY_COMBO = None        # Hammerspoon handles the global key
else:
    HOTKEY_LABEL = "Ctrl + Alt + F9"
    TK_HOTKEY = "<Control-Alt-F9>"
    GLOBAL_HOTKEY_COMBO = "<ctrl>+<alt>+<f9>"

# Model settings

# MODEL_SIZE: which Whisper model to load.
# Common values: "tiny", "base", "small", "medium", "large-v2", "large-v3"
# - Smaller models (tiny/base/small) → faster, use less RAM, but less accurate.
# - Larger models (medium/large-*) → slower, use less RAM, but more accurate.
# You can change this string to pick a different trade-off.
MODEL_SIZE = "medium"

# DEVICE: where to run the model.
# - "cpu" → works everywhere, but slower.
# - "cuda" → use NVIDIA GPU if you have one (requires CUDA drivers).
# - "auto" → let faster-whisper pick automatically (GPU if available, else CPU).
DEVICE = "cpu"

# COMPUTE_TYPE: numeric precision / quantization used by faster-whisper.
# Typical options:
# * "int8" → good default for CPU, low RAM usage, slower.
# * "int8_float16" → mixed precision, still memory-friendly.
# * "float16" → good for GPU, fast, needs FP16 support.
# * "float32" → highest precision, most RAM, usually overkill.
# You can tweak this if you want faster speed or lower memory usage.
COMPUTE_TYPE = "int8"

# SAMPLE_RATE: audio sampling rate in Hz.
# Whisper is trained for 16000 Hz, so 16000 is the safest choice.
# Only change this if you know what you are doing and keep recorder/config in sync.
SAMPLE_RATE = 16000

# CONFIG_PATH: path to the JSON file where Dictaria stores user settings
# (currently only the last active language).
# You can change the filename or directory if you want separate profiles.
CONFIG_PATH = os.path.expanduser("~/.dictaria_config.json")


# Theme (dark / slate)
THEME = {
    "root_bg": "#0f0f0f",
    "topbar_bg": "#0f0f0f",
    "topbar_fg": "#f1f5f9",
    "card_bg": "#1e293b",
    "border_color": "#f1f5f9",
    "text_frame_bg": "#1e293b",
    "text_box_bg": "#0D1116",
    "text_fg": "#f1f5f9",
    "record_idle_fill": "#d61d1d",
    "record_idle_outline": "#ef4444",
    "record_active_fill": "#fca5a5",
    "record_active_outline": "#dc2626",
    "record_disabled_fill": "#334155",
    "record_disabled_outline": "#475569",
    "pin_active_fg": "#ffffff",
    "pin_inactive_fg": "#a4a4a4",
    "scrollbar_trough": "#000000",
    "scrollbar_thumb": "#334155",
    "speaker_active_fg": "#e5e554", 
    "speaker_inactive_fg": "#a4a4a4", 
}

# Language definitions using NamedTuple for better structure
class Language(NamedTuple):
    code: str
    flag: str
    name: str
    
LANG_DEFS: Dict[str, Language] = {
    "en": Language("en", "🇬🇧", "English"),
    "zh": Language("zh", "🇨🇳", "中文"),
    "es": Language("es", "🇪🇸", "Español"),
    "ja": Language("ja", "🇯🇵", "日本語"), 
    "fr": Language("fr", "🇫🇷", "Français"), 
    "de": Language("de", "🇩🇪", "Deutsch"), 
    "it": Language("it", "🇮🇹", "Italiano"), 
    "pt": Language("pt", "🇵🇹", "Português"), 
    "ru": Language("ru", "🇷🇺", "Русский"), 
    "ko": Language("ko", "🇰🇷", "한국어"), 
}

LANG_CODES: List[str] = list(LANG_DEFS.keys())
LANG_OPTIONS: List[str] = [f"{v.name} {v.flag}" for v in LANG_DEFS.values()]

# UI messages
MSG_MODEL_READY = f"[Dictaria Ready. Click REC button or Press {HOTKEY_LABEL} to dictate]"
MSG_LOADING_MODEL = "[Initializing Dictaria... please wait]"
MSG_SELECT_LANG = "[Please select a language first]"
MSG_LISTENING = "[Listening...]"
MSG_PROCESSING = "[Transcribing...]"
MSG_NO_AUDIO = "[Audio too short or silent]"
MSG_ERROR = "[Error: {}]"
MSG_COPIED = "[Copied to clipboard]"

# --- END CONSTANTS MODULE ---


# --------------------
# CONFIGURATION MANAGER
# --------------------
class ConfigManager:
    """Handles loading and saving application configuration (e.g., active language)."""

    def __init__(self, path: str, default_lang_code: str):
        self.path = path
        self.default_lang_code = default_lang_code
        self.active_language: str = default_lang_code
        self._load()

    def _load(self):
        """Load the last used language from the config file."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    data = json.load(f)
                    # Use .get with default
                    loaded_lang = data.get("active", self.default_lang_code)
                    if loaded_lang in LANG_CODES:
                        self.active_language = loaded_lang
            except Exception as e:
                print(f"Config Load Error: {e}")

    def save(self):
        """Persist only the active language."""
        data = {"active": self.active_language}
        try:
            with open(self.path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Config Save Error: {e}")


# --------------------
# AUDIO RECORDER
# --------------------
class AudioRecorder:
    """Handles low-level audio capture using sounddevice."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.queue = queue.Queue()
        self.stream = None
        self.is_recording = False

    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback function executed for each audio block."""
        if status:
            # Print status but don't block the thread
            print(f"Audio Status: {status}") 
        self.queue.put(indata.copy())

    def start(self):
        """Start streaming from the default input device."""
        if self.is_recording:
            return
        
        # Clear any previous data immediately before starting
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
            self.is_recording = True
            print("Audio stream started.")
        except Exception as e:
            print(f"Failed to start audio stream: {e}")
            self.is_recording = False

    def stop(self) -> np.ndarray | None:
        """Stop the stream and return a single NumPy array with the audio."""
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

        # Concatenate audio data
        return np.concatenate(chunks, axis=0)


# --------------------
# MAIN APPLICATION
# --------------------
class DictariaApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = THEME
        
        # Concurrency setup: Use a thread pool for background tasks
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

        # State management
        self.config_manager = ConfigManager(CONFIG_PATH, LANG_CODES[0])
        self.active_language = self.config_manager.active_language
        self.recorder = AudioRecorder(sample_rate=SAMPLE_RATE)
        self.model = None
        self.model_loading = True
        self.is_pinned = False
        self.is_collapsed = False
        self.is_speaker_active = True # New state for speaker icon, default is active

        # Size management for collapse/expand
        self.INITIAL_SIZE = "300x400"
        self.FULL_MIN_WIDTH = 280
        self.FULL_MIN_HEIGHT = 350
        self.last_expanded_width = 0
        self.last_expanded_height = 0

        self.keyboard_listener = None # pynput global hotkey listener

        self.build_ui()
        self.apply_config_to_ui()

        # Submit model loading to the executor
        self.executor.submit(self._load_model_task)

        if IS_MAC:
            start_hammerspoon_listener(self)
        else:
            self.start_pynput_hotkey_listener()
            
        # Store initial expanded size after UI is built
        self.root.update_idletasks()
        self.last_expanded_width = self.root.winfo_width()
        self.last_expanded_height = self.root.winfo_height()


    # --------------------
    # Global hotkey (pynput, non-mac)
    # --------------------
    def start_pynput_hotkey_listener(self):
        """Start a pynput GlobalHotKeys listener on non-mac systems."""
        # Conditional import check for pynput
        if not globals().get('keyboard'): 
            print("[System] Global hotkey disabled (pynput missing).")
            return
        
        if not GLOBAL_HOTKEY_COMBO:
            return

        def on_activate():
            # Use root.after to safely interact with the Tkinter main thread
            self.root.after(0, self.toggle_record)

        try:
            # keyboard is imported by main() and set in globals()
            keyboard = globals().get('keyboard') 
            self.keyboard_listener = keyboard.GlobalHotKeys(
                {GLOBAL_HOTKEY_COMBO: on_activate}
            )
            self.keyboard_listener.start()
            print(f"[System] pynput GlobalHotKeys started for combo: {GLOBAL_HOTKEY_COMBO}")
        except Exception as e:
            print(f"[System] Error starting pynput listener: {e}")
            self.keyboard_listener = None

    # --------------------
    # UI CONSTRUCTION (Refactored and simplified)
    # --------------------
    def build_ui(self):
        self.root.geometry(self.INITIAL_SIZE)
        self.root.minsize(self.FULL_MIN_WIDTH, self.FULL_MIN_HEIGHT)
        self.root.configure(bg=self.theme["root_bg"])
        self.root.title("Dictaria")

        # In-window hotkey binding
        self.root.bind_all(TK_HOTKEY, lambda e: self.toggle_record())

        # Main Layout Frame
        self.main_frame = tk.Frame(self.root, bg=self.theme["root_bg"])
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Top Bar: Pin | Speaker | Collapse | Expander | Language Dropdown
        self.controls_frame = tk.Frame(self.main_frame, bg=self.theme["root_bg"])
        self.controls_frame.pack(fill="x", pady=(0, 2))
        
        # Default (Expanded) Layout:
        # 0: Pin | 1: Speaker | 2: Collapse | 3: Expander (Weight 1) | 4: Language Dropdown
        self.controls_frame.columnconfigure(3, weight=1) # The standard expander column
        
        self._build_control_buttons()

        # Record Button Frame
        self.record_button_frame = tk.Frame(self.main_frame, bg=self.theme["root_bg"])
        self.record_button_frame.pack(pady=(6, 8))
        self._build_record_canvas()

        # Text area (only in expanded mode)
        self.text_frame = tk.Frame(self.main_frame, bg=self.theme["text_frame_bg"])
        self.text_frame.pack(fill="both", expand=True, pady=(0, 0))
        self._build_text_box()

        self.append_system(MSG_LOADING_MODEL)
        
    def _build_control_buttons(self):
        # Pin button (Column 0 - Left, Grouped)
        self.btn_pin = tk.Canvas(self.controls_frame, width=20, height=20, bg=self.theme["root_bg"], highlightthickness=0, cursor="arrow")
        self.btn_pin.grid(row=0, column=0, sticky="w", padx=(0, 2))
        self.pin_text = self.btn_pin.create_text(10, 10, text="⦾", font=("Helvetica", 14), fill=self.theme["pin_inactive_fg"])
        self.btn_pin.bind("<Button-1>", lambda e: self.toggle_pin())
        
        # Speaker Icon (⟟/⦲) button (Column 1 - Grouped)
        self.btn_speaker = tk.Canvas(self.controls_frame, width=30, height=20, bg=self.theme["root_bg"], highlightthickness=0, cursor="arrow")
        self.btn_speaker.grid(row=0, column=1, sticky="w", padx=(0, 5)) 
        # Initial icon is active (⟟)
        color = self.theme["speaker_active_fg"] if self.is_speaker_active else self.theme["speaker_inactive_fg"]
        icon = "⟟" if self.is_speaker_active else "⦲"
        self.speaker_text = self.btn_speaker.create_text(15, 10, text=icon, font=("Helvetica", 12, "bold"), fill=color)
        self.btn_speaker.bind("<Button-1>", lambda e: self.toggle_speaker_icon())

        # Collapse button (▵/▿) (Column 2 - Grouped)
        self.btn_collapse = tk.Canvas(self.controls_frame, width=20, height=20, bg=self.theme["root_bg"], highlightthickness=0, cursor="arrow")
        self.btn_collapse.grid(row=0, column=2, sticky="w", padx=(2, 10)) 
        # Initial icon is expanded (▿)
        self.collapse_text = self.btn_collapse.create_text(10, 10, text="▿", font=("Helvetica", 14), fill=self.theme["pin_inactive_fg"])
        self.btn_collapse.bind("<Button-1>", lambda e: self.toggle_collapse())
        
        # Language dropdown (Column 4 - Far Right)
        self.lang_var = tk.StringVar(self.controls_frame)
        self.lang_var.trace_add("write", self.set_active_language_from_menu)

        self.option_menu_lang = tk.OptionMenu(self.controls_frame, self.lang_var, *LANG_OPTIONS)
        self.option_menu_lang.config(
            bg=self.theme["topbar_bg"], fg=self.theme["topbar_fg"], activebackground=self.theme["border_color"],
            activeforeground=self.theme["topbar_fg"], bd=0, relief=tk.FLAT, font=("Helvetica", 10),
        )
        menu = self.option_menu_lang["menu"]
        menu.config(bg=self.theme["topbar_bg"], fg=self.theme["topbar_fg"], bd=0, activebackground=self.theme["border_color"], activeforeground=self.theme["topbar_fg"])
        # Column 3 is the Expander, pushing this to Column 4
        self.option_menu_lang.grid(row=0, column=4, sticky="e", pady=2, padx=5)

    def _build_record_canvas(self):
        self.canvas_btn = tk.Canvas(self.record_button_frame, width=60, height=60, bg=self.theme["root_bg"], highlightthickness=0, bd=0)
        self.canvas_btn.pack(pady=0)
        self.record_indicator = self.canvas_btn.create_oval(4, 4, 56, 56,
            fill=self.theme["record_disabled_fill"],
            outline=self.theme["record_disabled_outline"],
            width=2,
        )
        self.canvas_btn.bind("<Button-1>", lambda e: self.toggle_record())
        self.canvas_btn.bind("<Configure>", self._on_record_canvas_resize)

    def _build_text_box(self):
        self.text_box = scrolledtext.ScrolledText(
            self.text_frame, wrap=tk.WORD, font=("Helvetica", 11),
            bg=self.theme["text_box_bg"], fg=self.theme["text_fg"],
            insertbackground="white", bd=0, padx=10, pady=10,
        )
        self.text_box.pack(fill="both", expand=True)
        
        # Configure scrollbar style (handle potential errors gracefully)
        try:
            self.text_box.vbar.config(
                bg=self.theme["scrollbar_thumb"],
                troughcolor=self.theme["scrollbar_trough"],
                activebackground=self.theme["border_color"],
                highlightthickness=0,
                bd=0,
            )
        except Exception:
            pass

        self.text_box.tag_config("sys", foreground=self.theme["record_idle_fill"], font=("Helvetica", 10, "italic"))
        self.text_box.tag_config("error", foreground="#ef4444", font=("Helvetica", 10, "bold"))


    def _on_record_canvas_resize(self, event):
        """Keep the REC circle perfectly round and centered."""
        if not hasattr(self, "record_indicator"):
            return
        size = min(event.width, event.height) - 4
        if size <= 0:
            return
        x0 = (event.width - size) / 2
        y0 = (event.height - size) / 2
        x1 = x0 + size
        y1 = y0 + size
        self.canvas_btn.coords(self.record_indicator, x0, y0, x1, y1)

    # --------------------
    # COLLAPSE / EXPAND LOGIC (Corrected Distributed Spacing only on Collapse)
    # --------------------
    def toggle_collapse(self):
        """Toggle between full view and ultra-compact view, applying distributed spacing when collapsed."""
        
        if not self.is_collapsed:
            # Transition to collapsed: Save current expanded size
            self.root.update_idletasks()
            self.last_expanded_width = self.root.winfo_width()
            self.last_expanded_height = self.root.winfo_height()
            
            # 1. HIDE components
            self.option_menu_lang.grid_remove()
            self.text_frame.pack_forget()
            
            # 2. APPLY DISTRIBUTED LAYOUT FOR COLLAPSED STATE:
            # Current (Expanded) layout: 0:Pin | 1:Speaker | 2:Collapse | 3:Expander | 4:Language
            
            # A. Change icon grid positions and stickiness to span columns 0, 2, 4
            self.btn_pin.grid(row=0, column=0, sticky="w", padx=(0, 0)) # Left
            self.btn_speaker.grid(row=0, column=2, sticky="", padx=(0, 0)) # Center (no sticky for center alignment)
            self.btn_collapse.grid(row=0, column=4, sticky="e", padx=(0, 0)) # Right
            
            # B. Reconfigure Expander Columns:
            # - Remove weight from Column 3 (original expander).
            self.controls_frame.columnconfigure(3, weight=0)
            # - Add weight to Column 1 (between Pin and Speaker) and Column 3 (between Speaker and Collapse)
            self.controls_frame.columnconfigure(1, weight=1) 
            self.controls_frame.columnconfigure(3, weight=1) 
            
            # 3. Compact paddings and recalculate minimum size
            self.controls_frame.pack_configure(pady=(0, 0))
            self.main_frame.pack_configure(padx=4, pady=4)
            self.record_button_frame.pack_configure(pady=(0, 12))
            
            self.root.update_idletasks()
            # Calculate required size for controls frame
            icon_width = self.btn_pin.winfo_reqwidth() + self.btn_speaker.winfo_reqwidth() + self.btn_collapse.winfo_reqwidth()
            # Estimate minimum width (icon width + minimum padding/expander space)
            width = max(icon_width + 40, 200) + 8 
            
            height = (
                self.controls_frame.winfo_reqheight()
                + self.record_button_frame.winfo_reqheight()
                + 8 # +8 for main_frame padding
            )
            
            self.root.geometry(f"{width}x{height}")
            self.root.minsize(width, height)

            # Change collapse icon to minimized (▵)
            self.btn_collapse.itemconfig(self.collapse_text, text="▵")
            
        else:
            # Transition to expanded: Restore grouped icons and language menu
            
            # 1. RESTORE GROUPED LAYOUT FOR EXPANDED STATE:
            # A. Restore icon grid positions (0, 1, 2) and stickiness
            self.btn_pin.grid(row=0, column=0, sticky="w", padx=(0, 2))
            self.btn_speaker.grid(row=0, column=1, sticky="w", padx=(0, 5))
            self.btn_collapse.grid(row=0, column=2, sticky="w", padx=(2, 10))
            
            # B. Restore Expander Columns:
            # - Remove weight from centering columns 1 (between Pin and Speaker).
            self.controls_frame.columnconfigure(1, weight=0) 
            # - Remove weight from centering columns 3 (between Speaker and Collapse) 
            #   (This column index 3 is reused below as the main expander).
            self.controls_frame.columnconfigure(3, weight=0) 
            # - Restore Column 3 as the single expander that pushes Language (Col 4)
            self.controls_frame.columnconfigure(3, weight=1) 
            
            # 2. RESTORE COMPONENTS
            self.option_menu_lang.grid(row=0, column=4, sticky="e", pady=2, padx=5)
            self.text_frame.pack(fill="both", expand=True, pady=(0, 0))

            self.controls_frame.pack_configure(pady=(0, 2))
            self.main_frame.pack_configure(padx=5, pady=5)
            self.record_button_frame.pack_configure(pady=(6, 8))

            # 3. Restore expanded window size and minimum
            width = max(self.last_expanded_width, self.FULL_MIN_WIDTH)
            height = max(self.last_expanded_height, self.FULL_MIN_HEIGHT)
            self.root.geometry(f"{width}x{height}")
            self.root.minsize(self.FULL_MIN_WIDTH, self.FULL_MIN_HEIGHT)
            self.root.update_idletasks()

            # Change collapse icon to expanded (▿)
            self.btn_collapse.itemconfig(self.collapse_text, text="▿")
            
        self.is_collapsed = not self.is_collapsed

    # --------------------
    # SPEAKER ICON / AUDIO FEEDBACK
    # --------------------
    def _play_pip_sound(self):
        """Plays a short, soft 'pip' sound if the speaker is active, ensuring thread safety."""
        if not self.is_speaker_active:
            return

        # Simple 880 Hz sine wave for 50ms (higher pitched pip)
        duration = 0.1
        freq = 880 # Higher frequency for an acute sound
        amplitude = 0.9 # Keep it soft
        
        # Generate the audio signal
        t = np.linspace(0., duration, int(duration * SAMPLE_RATE), endpoint=False)
        waveform = amplitude * np.sin(2. * np.pi * freq * t)
        
        # The actual play task must run in a thread separate from the main Tkinter loop
        def safe_play_task():
            try:
                # Use default output device
                sd.play(waveform.astype(np.float32), samplerate=SAMPLE_RATE)
                sd.wait() # Wait until the sound has finished playing
            except Exception as e:
                print(f"[System] Warning: Could not play pip sound: {e}")
        
        # Start the playback thread (daemon=True means it won't block program exit)
        threading.Thread(target=safe_play_task, daemon=True).start()
        
    def toggle_speaker_icon(self):
        """Toggle the speaker icon state and update its color and symbol."""
        self.is_speaker_active = not self.is_speaker_active
        self._update_speaker_icon_style()

    def _update_speaker_icon_style(self):
        """Updates the color and symbol of the speaker icon (⟟/⦲)."""
        color = self.theme["speaker_active_fg"] if self.is_speaker_active else self.theme["speaker_inactive_fg"]
        icon = "⟟" if self.is_speaker_active else "⦲"
        self.btn_speaker.itemconfig(self.speaker_text, fill=color, text=icon)


    # --------------------
    # LANGUAGE / CONFIG LOGIC
    # --------------------
    def _get_lang_code_from_option(self, option_text: str) -> str:
        """Utility to map UI option text back to language code."""
        # Find the language name part before the flag
        for code, defs in LANG_DEFS.items():
            if option_text.startswith(defs.name):
                return code
        return LANG_CODES[0]

    def set_active_language_from_menu(self, *args):
        selected_option = self.lang_var.get()
        new_code = self._get_lang_code_from_option(selected_option)

        if new_code != self.active_language:
            self.active_language = new_code
            self.config_manager.active_language = new_code
            self.config_manager.save()
            self.append_system(f"[Language set to: {LANG_DEFS[new_code].name}]")
            self.update_record_button_style()

    def apply_config_to_ui(self):
        """Set initial UI state based on loaded config."""
        if self.active_language in LANG_DEFS:
            defs = LANG_DEFS[self.active_language]
            active_option = f"{defs.name} {defs.flag}"
            if active_option in LANG_OPTIONS:
                self.lang_var.set(active_option)
        else:
            # Fallback to default if active_language is invalid
            self.active_language = LANG_CODES[0]
            self.lang_var.set(LANG_OPTIONS[0])
            
        self.update_record_button_style()
        self._update_speaker_icon_style() # Ensure initial speaker icon style is set

    # --------------------
    # PIN / MODEL / RECORDING LOGIC
    # --------------------
    def toggle_pin(self):
        """Toggle window always-on-top."""
        self.is_pinned = not self.is_pinned
        # -topmost is the Tkinter standard for always-on-top
        self.root.attributes("-topmost", self.is_pinned)

        icon = "⦿" if self.is_pinned else "⦾"
        color = self.theme["pin_active_fg"] if self.is_pinned else self.theme["pin_inactive_fg"]
        self.btn_pin.itemconfig(self.pin_text, text=icon, fill=color)

    def _load_model_task(self):
        """Load the Whisper model in a background thread using the executor."""
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
        """Start or stop recording and trigger transcription."""
        if self.model_loading:
            self.append_system(MSG_LOADING_MODEL, tag="error")
            return

        if self.active_language is None:
            self.append_system(MSG_SELECT_LANG, tag="error")
            return

        if not self.recorder.is_recording:
            # Start recording
            self.recorder.start()
            self.update_record_button_style()
            self.append_system(MSG_LISTENING)
        else:
            # Stop recording and launch transcription
            audio = self.recorder.stop()
            self.update_record_button_style() # Update style back to idle

            if audio is None or len(audio) < SAMPLE_RATE * 0.5: # 0.5 sec threshold
                self.append_system(MSG_NO_AUDIO)
                return

            lang = self.active_language
            # Submit transcription to the executor
            self.executor.submit(self._transcribe_task, audio, lang)


    def _transcribe_task(self, audio: np.ndarray, lang: str):
        """Background transcription task using faster-whisper."""
        self.safe_append_system(MSG_PROCESSING)

        tmp_name = None
        full_text = ""
        try:
            # Use tempfile.NamedTemporaryFile for safer file handling
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_name = tmp.name
            
            sf.write(tmp_name, audio, SAMPLE_RATE)
            
            segments, info = self.model.transcribe(
                tmp_name,
                language=lang,
                beam_size=5,
                condition_on_previous_text=False,
            )
            full_text = " ".join(seg.text.strip() for seg in segments).strip()

            if full_text:
                self.root.after(0, lambda t=full_text: self.safe_append_and_copy(t))
            else:
                self.safe_append_system(MSG_NO_AUDIO)
        except Exception as e:
            self.safe_append_system(MSG_ERROR.format(e), tag="error")
        finally:
            # Clean up temporary file
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError as e:
                    print(f"Error removing temp file {tmp_name}: {e}")
            
            # Play the soft pip sound when transcription is finished - SCHEDULED ON MAIN THREAD
            self.root.after(0, self._play_pip_sound)


    # --------------------
    # UI HELPERS (Ensuring thread safety with root.after)
    # --------------------
    def safe_append_system(self, text: str, tag: str = "sys"):
        """Call append_system safely from a background thread."""
        self.root.after(0, lambda: self.append_system(text, tag))

    def safe_append_and_copy(self, text: str):
        """Append transcribed text and copy it to the clipboard."""
        self.text_box.insert(tk.END, text + "\n")
        self.text_box.see(tk.END)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.append_system(MSG_COPIED)
        except tk.TclError:
            self.append_system("[Warning: Failed to copy to clipboard]", tag="error")

    def append_system(self, text: str, tag: str = "sys"):
        """Append a system/status message to the text box."""
        # Ensure the entire message is treated as a single block
        self.text_box.insert(tk.END, text + "\n", tag)
        self.text_box.see(tk.END)

    def update_record_button_style(self):
        """Update the REC button color based on the application state."""
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
def start_hammerspoon_listener(app_instance: DictariaApp):
    """Poll a signal file created by Hammerspoon and toggle record when it appears."""
    # Clean up old file if it exists
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
            # Use root.after for thread safety
            app_instance.root.after(0, app_instance.toggle_record)

        # Poll every 100ms
        app_instance.root.after(100, check_signal)

    print(f"Hammerspoon Listener started (file polling) on: {SIGNAL_FILE}")
    check_signal()


# --------------------
# ENTRY POINT
# --------------------
def main():
    # Handle pynput import for non-Mac systems here
    if not IS_MAC:
        try:
            from pynput import keyboard
            globals()['keyboard'] = keyboard # Make it available in globals for DictariaApp
            print("[System] pynput imported successfully for non-Mac systems.")
        except ImportError:
            print("[System] Warning: pynput not installed. Global hotkey will not work on this system.")
            globals()['keyboard'] = None
    else:
        globals()['keyboard'] = None


    root = tk.Tk()

    # Optional window icon
    try:
        # A simple method to handle paths relative to the script
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.exists(icon_path):
            img = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, img)
    except Exception:
        pass

    app = DictariaApp(root)

    def on_closing():
        # Stop pynput listener gracefully
        if app.keyboard_listener:
            try:
                app.keyboard_listener.stop()
                print("pynput listener stopped.")
            except Exception:
                pass
        
        # Shutdown executor
        app.executor.shutdown(wait=False)
        
        # Destroy main window
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    # Check for sounddevice and soundfile before running main
    try:
        # This check is just to ensure the basic audio libraries are available
        sd.query_devices(kind='output') 
    except Exception as e:
        print(f"FATAL ERROR: sounddevice or soundfile is missing or configuration error: {e}")
        print("Please ensure sounddevice and soundfile are installed and a working audio output is available.")
        sys.exit(1)
        
    main()

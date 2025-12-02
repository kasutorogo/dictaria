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
from faster_whisper import WhisperModel

import tkinter as tk
from tkinter import scrolledtext, PhotoImage

# --------------------
# CONSTANTS & CONFIGURATION
# --------------------

# Hotkey settings
SIGNAL_FILE = "/tmp/dictaria_signal_f9.txt"  # Used only on macOS with Hammerspoon
IS_MAC = sys.platform == "darwin"

if IS_MAC:
    HOTKEY_LABEL = "Cmd + Option + F9"
    TK_HOTKEY = "<Command-Option-F9>"
    GLOBAL_HOTKEY_COMBO = None
else:
    HOTKEY_LABEL = "Ctrl + Alt + F9"
    TK_HOTKEY = "<Control-Alt-F9>"
    GLOBAL_HOTKEY_COMBO = "<ctrl>+<alt>+<f9>"

# Model settings
MODEL_SIZE = "medium"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
SAMPLE_RATE = 16000
INTERNAL_MIC_HINT = "MacBook"
CONFIG_PATH = os.path.expanduser("~/.dictaria_config.json")

# Theme
THEME = {
    "root_bg": "#323232",
    "topbar_bg": "#323232",
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
MSG_MODEL_READY = f"[Dictaria Ready. Click REC or Press {HOTKEY_LABEL}]"
MSG_LOADING_MODEL = "[Initializing Dictaria... please wait]"
MSG_SELECT_LANG = "[Please select a language first]"
MSG_LISTENING = "[Listening...]"
MSG_STOPPING = "[Finalizing audio...]"  
MSG_PROCESSING = "[Transcribing...]"
MSG_NO_AUDIO = "[Audio too short or silent]"
MSG_ERROR = "[Error: {}]"
MSG_COPIED = "[Copied to clipboard]"

# --------------------
# CONFIGURATION MANAGER
# --------------------
class ConfigManager:
    def __init__(self, path: str, default_lang_code: str):
        self.path = path
        self.default_lang_code = default_lang_code
        self.active_language: str = default_lang_code
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    data = json.load(f)
                    loaded_lang = data.get("active", self.default_lang_code)
                    if loaded_lang in LANG_CODES:
                        self.active_language = loaded_lang
            except Exception as e:
                print(f"Config Load Error: {e}")

    def save(self):
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
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.queue = queue.Queue()
        self.stream = None
        self.is_recording = False

    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            print(f"Audio Status: {status}")
        self.queue.put(indata.copy())

    def start(self):
        if self.is_recording:
            return
        
        with self.queue.mutex:
            self.queue.queue.clear()
            
        try:
            input_device = None
            if IS_MAC and INTERNAL_MIC_HINT:
                try:
                    devices = sd.query_devices()
                    hint_lower = INTERNAL_MIC_HINT.lower()
                    for idx, dev in enumerate(devices):
                        if dev.get("max_input_channels", 0) > 0 and hint_lower in dev.get("name", "").lower():
                            input_device = idx
                            print(f"Using forced macOS input device: {dev['name']}")
                            break
                except Exception as e:
                    print(f"Device query warning: {e}")

            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._callback,
                device=input_device,
            )
            self.stream.start()
            self.is_recording = True
        except Exception as e:
            print(f"Failed to start stream: {e}")
            self.is_recording = False
            raise e

    def stop(self) -> np.ndarray | None:
        """Stops stream. WARNING: This can be slow, call off main thread."""
        if not self.is_recording:
            return None

        self.is_recording = False
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
        except Exception as e:
            print(f"Error closing stream: {e}")

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
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = THEME
        
        # Concurrency: ThreadPool for tasks preventing UI freeze
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

        self.config_manager = ConfigManager(CONFIG_PATH, LANG_CODES[0])
        self.active_language = self.config_manager.active_language
        self.recorder = AudioRecorder(sample_rate=SAMPLE_RATE)
        
        self.model = None
        self.model_loading = True
        self.is_pinned = False
        self.is_collapsed = False
        self.is_speaker_active = True
        
        # Flag to prevent double clicking or race conditions while processing audio
        self.is_processing = False

        self.INITIAL_SIZE = "300x400"
        self.FULL_MIN_WIDTH = 280
        self.FULL_MIN_HEIGHT = 350
        
        self.build_ui()
        self.apply_config_to_ui()

        # Load model in background
        self.executor.submit(self._load_model_task)

        if IS_MAC:
            self.start_hammerspoon_listener()
        else:
            self.start_pynput_hotkey_listener()
            
        self.root.update_idletasks()
        self.last_expanded_width = self.root.winfo_width()
        self.last_expanded_height = self.root.winfo_height()

    def start_pynput_hotkey_listener(self):
        try:
            from pynput import keyboard
            if GLOBAL_HOTKEY_COMBO:
                def on_activate():
                    # Thread-safe call to Tkinter
                    self.root.after(0, self.toggle_record)
                    
                self.keyboard_listener = keyboard.GlobalHotKeys({GLOBAL_HOTKEY_COMBO: on_activate})
                self.keyboard_listener.start()
                print(f"Global hotkey active: {GLOBAL_HOTKEY_COMBO}")
        except ImportError:
            print("pynput not found. Global hotkey disabled.")
        except Exception as e:
            print(f"Hotkey error: {e}")

    # --------------------
    # HAMMERSPOON LISTENER (Fixed & Completed)
    # --------------------
    def start_hammerspoon_listener(self):
        """Poll for file existence safely using root.after to avoid freezing."""
        def check_signal():
            if os.path.exists(SIGNAL_FILE):
                try:
                    os.remove(SIGNAL_FILE)
                    print("Signal received from Hammerspoon")
                    self.toggle_record()
                except OSError as e:
                    print(f"Error removing signal file: {e}")
            # Check again in 200ms
            self.root.after(200, check_signal)
            
        # Start the polling loop
        check_signal()

    # --------------------
    # UI BUILD
    # --------------------
    def build_ui(self):
            self.root.geometry(self.INITIAL_SIZE)
            self.root.minsize(self.FULL_MIN_WIDTH, self.FULL_MIN_HEIGHT)
            self.root.configure(bg=self.theme["root_bg"])
            self.root.title("Dictaria")

            try:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "icon.png")
                self.icon_image = PhotoImage(file=icon_path) 
                self.root.iconphoto(True, self.icon_image) 
            except Exception as e:
                print(f"Icon Load Warning: Could not load icon. Error: {e}")
            
            self.root.bind_all(TK_HOTKEY, lambda e: self.toggle_record())

            self.main_frame = tk.Frame(self.root, bg=self.theme["root_bg"])
            self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            self.controls_frame = tk.Frame(self.main_frame, bg=self.theme["root_bg"])
            self.controls_frame.pack(fill="x", pady=(0, 2))
            self.controls_frame.columnconfigure(3, weight=1)
            
            self._build_control_buttons()

            self.record_button_frame = tk.Frame(self.main_frame, bg=self.theme["root_bg"])
            self.record_button_frame.pack(pady=(6, 8))
            self._build_record_canvas()

            self.text_frame = tk.Frame(self.main_frame, bg=self.theme["text_frame_bg"])
            self.text_frame.pack(fill="both", expand=True)
            self._build_text_box()

            self.append_system(MSG_LOADING_MODEL)

    def _build_control_buttons(self):
        # Pin
        self.btn_pin = tk.Canvas(self.controls_frame, width=20, height=20, bg=self.theme["root_bg"], highlightthickness=0)
        self.btn_pin.grid(row=0, column=0, sticky="w", padx=(0, 2))
        self.pin_text = self.btn_pin.create_text(10, 10, text="⦾", font=("Helvetica", 14), fill=self.theme["pin_inactive_fg"])
        self.btn_pin.bind("<Button-1>", lambda e: self.toggle_pin())
        
        # Speaker
        self.btn_speaker = tk.Canvas(self.controls_frame, width=30, height=20, bg=self.theme["root_bg"], highlightthickness=0)
        self.btn_speaker.grid(row=0, column=1, sticky="w", padx=(0, 5)) 
        self.speaker_text = self.btn_speaker.create_text(15, 10, text="⟟", font=("Helvetica", 12, "bold"), fill=self.theme["speaker_active_fg"])
        self.btn_speaker.bind("<Button-1>", lambda e: self.toggle_speaker_icon())

        # Collapse
        self.btn_collapse = tk.Canvas(self.controls_frame, width=20, height=20, bg=self.theme["root_bg"], highlightthickness=0)
        self.btn_collapse.grid(row=0, column=2, sticky="w", padx=(2, 10))
        self.collapse_text = self.btn_collapse.create_text(10, 10, text="▿", font=("Helvetica", 14), fill=self.theme["pin_inactive_fg"])
        self.btn_collapse.bind("<Button-1>", lambda e: self.toggle_collapse())
        
        # Lang
        self.lang_var = tk.StringVar(self.controls_frame)
        self.lang_var.trace_add("write", self.set_active_language_from_menu)
        self.option_menu_lang = tk.OptionMenu(self.controls_frame, self.lang_var, *LANG_OPTIONS)
        self.option_menu_lang.config(bg=self.theme["topbar_bg"], fg=self.theme["topbar_fg"], bd=0, highlightthickness=0)
        self.option_menu_lang["menu"].config(bg=self.theme["topbar_bg"], fg=self.theme["topbar_fg"])
        self.option_menu_lang.grid(row=0, column=4, sticky="e", pady=2, padx=5)

    def _build_record_canvas(self):
        self.canvas_btn = tk.Canvas(self.record_button_frame, width=60, height=60, bg=self.theme["root_bg"], highlightthickness=0, bd=0)
        self.canvas_btn.pack()
        self.record_indicator = self.canvas_btn.create_oval(4, 4, 56, 56, width=2)
        self.canvas_btn.bind("<Button-1>", lambda e: self.toggle_record())
        self.canvas_btn.bind("<Configure>", self._on_record_canvas_resize)

    def _build_text_box(self):
        self.text_box = scrolledtext.ScrolledText(
            self.text_frame, wrap=tk.WORD, font=("Helvetica", 11),
            bg=self.theme["text_box_bg"], fg=self.theme["text_fg"],
            insertbackground="white", bd=0, padx=10, pady=10
        )
        self.text_box.pack(fill="both", expand=True)
        self.text_box.tag_config("sys", foreground=self.theme["record_idle_fill"], font=("Helvetica", 10, "italic"))
        self.text_box.tag_config("error", foreground="#ef4444", font=("Helvetica", 10, "bold"))

    def _on_record_canvas_resize(self, event):
        size = min(event.width, event.height) - 4
        if size <= 0: return
        x0, y0 = (event.width - size)/2, (event.height - size)/2
        self.canvas_btn.coords(self.record_indicator, x0, y0, x0+size, y0+size)

    # --------------------
    # LOGIC - COLLAPSE / SPEAKER
    # --------------------
    def toggle_collapse(self):
        if not self.is_collapsed:
            self.root.update_idletasks()
            self.last_expanded_width = self.root.winfo_width()
            self.last_expanded_height = self.root.winfo_height()
            
            self.option_menu_lang.grid_remove()
            self.text_frame.pack_forget()
            
            # Distributed layout
            self.btn_pin.grid(row=0, column=0, sticky="w")
            self.btn_speaker.grid(row=0, column=2, sticky="")
            self.btn_collapse.grid(row=0, column=4, sticky="e")
            self.controls_frame.columnconfigure(3, weight=0)
            self.controls_frame.columnconfigure(1, weight=1)
            self.controls_frame.columnconfigure(3, weight=1)
            
            icon_w = 70
            w = max(icon_w + 40, 200)
            h = self.controls_frame.winfo_reqheight() + self.record_button_frame.winfo_reqheight() + 10
            self.root.geometry(f"{w}x{h}")
            self.btn_collapse.itemconfig(self.collapse_text, text="▵")
        else:
            self.btn_pin.grid(row=0, column=0, sticky="w", padx=(0, 2))
            self.btn_speaker.grid(row=0, column=1, sticky="w", padx=(0, 5))
            self.btn_collapse.grid(row=0, column=2, sticky="w", padx=(2, 10))
            self.controls_frame.columnconfigure(1, weight=0)
            self.controls_frame.columnconfigure(3, weight=1)
            
            self.option_menu_lang.grid(row=0, column=4, sticky="e")
            self.text_frame.pack(fill="both", expand=True)
            
            w = max(self.last_expanded_width, self.FULL_MIN_WIDTH)
            h = max(self.last_expanded_height, self.FULL_MIN_HEIGHT)
            self.root.geometry(f"{w}x{h}")
            self.btn_collapse.itemconfig(self.collapse_text, text="▿")
            
        self.is_collapsed = not self.is_collapsed

    def _play_pip_sound(self):
        if not self.is_speaker_active: return
        def safe_play_task():
            try:
                t = np.linspace(0., 0.1, int(0.1 * SAMPLE_RATE), endpoint=False)
                waveform = 0.5 * np.sin(2. * np.pi * 880 * t)
                sd.play(waveform.astype(np.float32), samplerate=SAMPLE_RATE)
                sd.wait()
            except Exception: pass
        threading.Thread(target=safe_play_task, daemon=True).start()

    def toggle_speaker_icon(self):
        self.is_speaker_active = not self.is_speaker_active
        self._update_speaker_icon_style()

    def _update_speaker_icon_style(self):
        color = self.theme["speaker_active_fg"] if self.is_speaker_active else self.theme["speaker_inactive_fg"]
        icon = "⟟" if self.is_speaker_active else "⦲"
        self.btn_speaker.itemconfig(self.speaker_text, fill=color, text=icon)

    # --------------------
    # LOGIC - CONFIG / MODEL
    # --------------------
    def set_active_language_from_menu(self, *args):
        txt = self.lang_var.get()
        for c, d in LANG_DEFS.items():
            if txt.startswith(d.name):
                self.active_language = c
                self.config_manager.active_language = c
                self.config_manager.save()
                self.append_system(f"[Language: {d.name}]")
                break
        self.update_record_button_style()

    def apply_config_to_ui(self):
        if self.active_language in LANG_DEFS:
            d = LANG_DEFS[self.active_language]
            self.lang_var.set(f"{d.name} {d.flag}")
        self.update_record_button_style()
        self._update_speaker_icon_style()

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.root.attributes("-topmost", self.is_pinned)
        icon = "⦿" if self.is_pinned else "⦾"
        color = self.theme["pin_active_fg"] if self.is_pinned else self.theme["pin_inactive_fg"]
        self.btn_pin.itemconfig(self.pin_text, text=icon, fill=color)

    def _load_model_task(self):
        try:
            print(f"Loading Model {MODEL_SIZE} on {DEVICE}...")
            self.model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
            self.model_loading = False
            self.safe_append_system(MSG_MODEL_READY)
            self.root.after(0, self.update_record_button_style)
        except Exception as e:
            self.safe_append_system(MSG_ERROR.format(e), "error")

    # --------------------
    # CORE RECORDING LOGIC (Optimized)
    # --------------------
    def toggle_record(self):
        # 1. Prevent actions if model loading or busy processing
        if self.model_loading:
            self.append_system(MSG_LOADING_MODEL, tag="error")
            return
        if self.is_processing:
            print("Busy processing, ignoring click.")
            return

        # 2. Start Recording (Safe on main thread usually)
        if not self.recorder.is_recording:
            try:
                self.recorder.start()
                self.update_record_button_style()
                self.append_system(MSG_LISTENING)
            except Exception as e:
                self.append_system(MSG_ERROR.format(e), "error")
        
        # 3. Stop Recording -> MOVE TO THREAD to prevent freeze
        else:
            self.is_processing = True # Lock UI logic
            self.append_system(MSG_STOPPING) 
            self.update_record_button_style() # Visual feedback immediately
            
            # Offload heavy stopping and transcription to background thread
            lang = self.active_language
            self.executor.submit(self._stop_and_transcribe_task, lang)

    def _stop_and_transcribe_task(self, lang: str):
        """Runs in background thread: Stops audio, concatenates, transcribes."""
        try:
            audio = self.recorder.stop()
            
            if audio is None or len(audio) < SAMPLE_RATE * 0.5:
                self.safe_append_system(MSG_NO_AUDIO)
                return

            self.safe_append_system(MSG_PROCESSING)
            
            # Transcription
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_name = tmp.name
            
            sf.write(tmp_name, audio, SAMPLE_RATE)
            
            segments, _ = self.model.transcribe(
                tmp_name, language=lang, beam_size=5, condition_on_previous_text=False
            )
            full_text = " ".join(seg.text.strip() for seg in segments).strip()
            
            if full_text:
                self.root.after(0, lambda: self.safe_append_and_copy(full_text))
            else:
                self.safe_append_system(MSG_NO_AUDIO)

            # Cleanup
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
                
            self.root.after(0, self._play_pip_sound)

        except Exception as e:
            self.safe_append_system(MSG_ERROR.format(e), "error")
        finally:
            # Unlock the UI
            self.is_processing = False
            self.root.after(0, self.update_record_button_style)

    # --------------------
    # HELPERS
    # --------------------
    def safe_append_system(self, text: str, tag: str = "sys"):
        self.root.after(0, lambda: self.append_system(text, tag))

    def safe_append_and_copy(self, text: str):
        self.text_box.insert(tk.END, text + "\n")
        self.text_box.see(tk.END)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.append_system(MSG_COPIED)
        except Exception:
            self.append_system("[Clipboard Error - Text only in window]", tag="error")

    def append_system(self, text: str, tag: str = "sys"):
        self.text_box.insert(tk.END, text + "\n", tag)
        self.text_box.see(tk.END)

    def update_record_button_style(self):
        if self.model_loading or self.is_processing:
            fill = self.theme["record_disabled_fill"]
            outline = self.theme["record_disabled_outline"]
        elif self.recorder.is_recording:
            fill = self.theme["record_active_fill"]
            outline = self.theme["record_active_outline"]
        else:
            fill = self.theme["record_idle_fill"]
            outline = self.theme["record_idle_outline"]

        self.canvas_btn.itemconfig(self.record_indicator, fill=fill, outline=outline)


def main():
    root = tk.Tk()
    app = DictariaApp(root)
    
    # Clean shutdown of threads
    def on_close():
        if app.recorder.is_recording:
            app.recorder.stop()
        app.executor.shutdown(wait=False)
        root.destroy()
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()

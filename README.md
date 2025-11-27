<p align="center">
  <img src="icon.png" alt="Dictaria icon" width="180">
</p>

# Dictaria 🎤 - Local Speech-to-Text Tool

Dictaria is a small desktop dictation app. Its **compact design** keeps it out of your way while you work.

It listens to your microphone, transcribes audio locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and dumps everything into a simple multi-language text window with a global hotkey.

---

## ✨ Features

* Records from the system default microphone.
* Local transcription with `faster-whisper` (`medium` model by default).
* **Automatically copies transcribed text to the system clipboard (portapapeles).**
* **Pin button** 📌 to keep the window **always on top** (primer plano).
* Multi-language support via a single dropdown:
    * Dictaria’s UI exposes 10 common ones by default: Spanish, English, Japanese, French, German, Italian, Portuguese, Chinese, Russian, Korean.
* Global hotkey:
    * macOS: **`Cmd + Option + F9` (Requires Hammerspoon)**
    * Windows / Linux: **`Ctrl + Alt + F9` (via pynput)**
* Simple UI:
    * **Compact and minimalist window size.**
    * Circular red button to start/stop recording.
    * Scrollable text area with all transcriptions.
    * Status messages in English: `[Listening...]`, `[Transcribing...]`, etc.
* Persistent config in `~/.dictaria_config.json`:
    * Last active language.

---

## 🛠️ Requirements & Installation

### Common Requirements

* **Python 3.10+** (3.11+ recommended).
* `pip` to install dependencies.
* Working audio input (microphone).
* Tkinter available for your Python build (for the GUI).

Python packages (also listed in `requirements.txt`):

* `faster-whisper`
* `sounddevice`
* `soundfile`
* `numpy`
* **macOS:** You **do not** need `pynput`. The hotkey is managed by Hammerspoon.
* **Windows/Linux:** You **do** need `pynput` for the global hotkey.

> Tkinter is usually bundled with the standard Python installers on macOS and Windows. On many Linux distros you must install the `tk` package from your system package manager (see below).

### Quick Install (All Platforms)

1.  Clone the repository:

    ```bash
    git clone [https://github.com/dnlcstr/dictaria.git](https://github.com/dnlcstr/dictaria.git)
    cd dictaria
    ```

2.  Create and activate a virtual environment (recommended):

    ```bash
    python -m venv .venv

    # macOS / Linux
    source .venv/bin/activate

    # Windows (PowerShell)
    .venv\Scripts\Activate.ps1
    ```

3.  Install dependencies:

    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

> **Note for macOS users:** The `requirements.txt` includes `pynput` for cross-platform compatibility. If you are only using the Hammerspoon method, you can safely ignore `pynput` installation warnings or use `pip install faster-whisper sounddevice soundfile numpy` instead.

4.  **Run Dictaria:**

    ```bash
    python dictaria.py
    ```

> On first launch, faster-whisper will download and load the medium model. This can take a bit of time.

---

## 🚨 Global Hotkey Setup for macOS

Since Dictaria relies on **Hammerspoon** for the global hotkey on macOS, you must follow these extra steps:

### 1. Install Hammerspoon

Download and install [Hammerspoon](https://www.hammerspoon.org/). It requires **Accessibility Permissions** to work.

### 2. Configure Hammerspoon

1.  Open the Hammerspoon Console (Hammer icon > *Open Console*).
2.  Open your Hammerspoon config file: `~/.hammerspoon/init.lua` (Hammer icon > *Open Config*).
3.  **Add the following Lua code** to your `init.lua` file:

    ```lua
    -- Dictaria Hotkey: Cmd + Option + F9 (communicates via a temporary file)
    local dictaria_hotkey = {"cmd", "alt"} 
    local dictaria_key = "f9"
    local signal_file = "/tmp/dictaria_signal_f9.txt" 

    hs.hotkey.bind(dictaria_hotkey, dictaria_key, function()
        -- Use 'touch' to create the signal file. Dictaria.py polls and deletes it.
        hs.task.new("/usr/bin/touch", nil, {signal_file}):start()
    end)

    hs.alert.show("Dictaria Hotkey (Cmd+Alt+F9) enabled.")
    ```
4.  **Reload** the configuration (Hammer icon > *Reload Config*). You should see the confirmation alert.

### 3. Permissions Check

* **Microphone:** System Settings → Privacy & Security → Microphone. Ensure your Terminal or Python launcher is enabled.
* **Hammerspoon:** System Settings → Privacy & Security → Accessibility. Ensure **Hammerspoon** is enabled.

---

## ▶️ How to Use

1.  **Start Dictaria:**
    ```bash
    cd dictaria
    source .venv/bin/activate   # or the Windows equivalent
    python dictaria.py
    ```

2.  Select your language in the dropdown menu (e.g., "Spanish 🇪🇸") to set it as the active language.

3.  **Start dictation** by clicking the red button or pressing the global hotkey:
    * macOS: **`Cmd + Option + F9`** (via Hammerspoon)
    * Windows / Linux: **`Ctrl + Alt + F9`**

4.  Press the hotkey again (or click the button) to stop recording and start transcription. **Once transcription is complete, the resulting text will automatically be copied to your clipboard (portapapeles).**

5.  Use the **Pin button** 📌 in the top-left corner to keep the Dictaria window over other applications.

---

## 💻 Configuration

Dictaria stores a tiny JSON file in your home directory: `~/.dictaria_config.json`.

* The last selected language is remembered automatically.
* Delete `~/.dictaria_config.json` if you want to reset the configuration.

---

## 🍏 macOS Notes

> **Important:** The global hotkey is handled by **Hammerspoon** (see the setup section above). The Python application no longer handles global input directly.

1.  **PortAudio (for `sounddevice`)**
    If you see audio-related errors, install PortAudio:
    ```bash
    brew install portaudio
    pip install --force-reinstall sounddevice
    ```

2.  **Microphone Permissions**
    Make sure your terminal (or app wrapper) has access:
    * System Settings → Privacy & Security → Microphone.

---

## 🪟 Windows Notes

1.  **Python & Tkinter**
    Install Python from `python.org` and check **“Add Python to PATH”**. Tkinter is included by default.

2.  **Microphone Permissions**
    On recent Windows: Settings → Privacy & security → Microphone. Enable access for desktop apps.

3.  **Global Hotkey**
    The hotkey is **`Ctrl + Alt + F9`** and is handled by the included `pynput` dependency.

---

## 🐧 Linux Notes

1.  **System Packages (Debian/Ubuntu)**
    Install required packages for audio and GUI:
    ```bash
    sudo apt update
    sudo apt install -y python3 python3-venv python3-tk \
                        libportaudio2 libsndfile1
    ```

2.  **Global Hotkey**
    The hotkey is **`Ctrl + Alt + F9`** and is handled by `pynput`. If your desktop environment intercepts this shortcut, rely on the in-window hotkey.

---

## ❓ FAQ

**Q: Does Dictaria work offline?**
A: Yes. After the model is downloaded the first time, transcription is local.

**Q: Can I use a different model (small, large-v3)?**
A: Yes. In `dictaria.py`, change `MODEL_SIZE = "medium"`.

**Q: How do I reset languages and favorites?**
A: Close Dictaria and delete `~/.dictaria_config.json`.

---

## Credits

* Core transcription technology provided by [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
* **macOS Hotkey solution via File Polling inspired by the Hammerspoon community.**
* Vibe-coded with assistance from Google's Gemini models and ChatGPT (GPT-5.1 Thinking).

## License

This project is licensed under the MIT License.

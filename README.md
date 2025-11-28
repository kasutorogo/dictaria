<p align="center">
  <img src="icon.png" alt="Dictaria icon" width="180">
</p>

# Dictaria 🎤 - Local Speech-to-Text Tool

Dictaria is a small, compact desktop dictation app. Its **minimalist design** keeps it out of your way while you work.

It listens to your microphone, transcribes audio locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and outputs the text into a simple, multi-language window, accessible via a global hotkey.

---

## ✨ Features

* Records from the system's default microphone.
* Local transcription using `faster-whisper`. It defaults to the **Whisper v3 medium model** for excellent accuracy.
* **Automatically copies the transcribed text to the system clipboard.**
* **Pin Button** (⦾/⦿) to keep the window **always on top** (foreground).
* **Speaker/Audio Feedback Button** (⟟/⦲): Toggles a soft audio "pip" sound that plays when the transcription is complete. By default, this is **active** (yellow color).
* **View Collapse Button (△/▽):** Allows you to **hide the text area** and minimize the window to a small, non-intrusive strip.
    * **Collapsed State Layout:** When collapsed, the three primary icons (Pin, Speaker, Collapse) are **horizontally distributed** across the top bar for quick access.
* Multi-language support via a single dropdown:
    * Dictaria’s UI exposes 10 common languages by default: English, Chinese, Spanish, Japanese, French, German, Italian, Portuguese, Russian, Korean.
* Global and In-Window hotkeys (see table below).
* Simple UI:
    * **Compact and minimalist window size.**
    * Circular red button to start/stop recording.
    * Scrollable text area containing all transcriptions.
    * Status messages in English: `[Listening...]`, `[Transcribing...]`, etc.
* Persistent configuration in `~/.dictaria_config.json`:
    * Remembers the last active language.

---

## ⌨️ Global Hotkey Behavior

| Platform | Global Hotkey (Active outside app) | In-Window Hotkey (Always available) | Requirements |
| :--- | :--- | :--- | :--- |
| **macOS** 🍎 | `Cmd + Option + F9` | `Cmd + Option + F9` | **Hammerspoon** setup. |
| **Windows / Linux** 🐧 | `Ctrl + Alt + F9` | `Ctrl + Alt + F9` | **`pynput`** installed. |

> **IMPORTANT NOTE (Windows/Linux):** The global hotkey relies on the Python library **`pynput`**. If `pynput` is not installed or encounters permission issues, Dictaria automatically **falls back to the in-window hotkey only**.

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
* **Windows/Linux:** You **do** need `pynput` for the global hotkey.
* **macOS:** You **do not** need `pynput` for the hotkey (handled by Hammerspoon).

> Tkinter is usually bundled with standard Python installers on macOS and Windows. On many Linux distros you must install the `tk` package from your system package manager (see below).

### Quick Install (All Platforms)

1.  Clone the repository:

    ```bash
    git clone [https://github.com/dnlcstr/dictaria.git](https://github.com/dnlcstr/dictaria.git)
    cd dictaria
    ```

2.  Create and activate a virtual environment (recommended):

    ```bash
    python -m venv .venv

    # macOS / Linux
    source .venv/bin/activate

    # Windows (PowerShell)
    .venv\Scripts\Activate.ps1
    ```

3.  Install dependencies:

    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

> On first launch, faster-whisper will download and load the medium model. This can take a bit of time.

4.  **Run Dictaria:**

    ```bash
    python dictaria.py
    ```

---

## 🚨 Global Hotkey Setup for macOS

Since Dictaria relies on **Hammerspoon** for the global hotkey on macOS, you must follow these extra steps:

### 1. Install Hammerspoon

Download and install [Hammerspoon](https://www.hammerspoon.org/). It requires **Accessibility Permissions** to function.

### 2. Configure Hammerspoon

1.  Open the Hammerspoon Console (Hammer icon > *Open Console*).
2.  Open your Hammerspoon config file: `~/.hammerspoon/init.lua` (Hammer icon > *Open Config*).
3.  **Add the following Lua code** to your `init.lua` file:

    ```lua
    -- Dictaria Hotkey: Cmd + Option + F9 (communicates via a temporary file)
    local dictaria_hotkey = {"cmd", "alt"}
    local dictaria_key = "f9"
    local signal_file = "/tmp/dictaria_signal_f9.txt" -- Must match SIGNAL_FILE in dictaria.py
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

1.  **Start Dictaria:**

    ```bash
    cd dictaria
    source .venv/bin/activate    # or the Windows equivalent
    python dictaria.py
    ```

2.  Select your language in the dropdown menu to set it as the active language.

3.  **Start dictation** by clicking the red button or pressing the global hotkey:
    * macOS: **`Cmd + Option + F9`** (via Hammerspoon)
    * Windows / Linux: **`Ctrl + Alt + F9`**

4.  Press the hotkey again (or click the button) to stop recording and start transcription. **Once transcription is complete, the resulting text will automatically be copied to your clipboard.**
    * If the **Speaker icon (~o~)** is yellow, you will hear a soft sound when the transcription finishes. Click the icon to toggle this audio feedback off (it will turn gray).

5.  Use the **Pin button** (⟟/⦲) in the top-left corner to keep the Dictaria window over other applications.

6.  Use the **Collapse button** (△/▽) in the top-right corner to **hide the text area** and minimize the window.

---

## 💻 Configuration

Dictaria stores a tiny JSON file in your home directory: `~/.dictaria_config.json`.

* The last selected language is remembered automatically.
* Delete `~/.dictaria_config.json` if you want to reset the configuration.

---

## 🍏 macOS Notes

> **Important:** The global hotkey is handled by **Hammerspoon** (see the setup section above). The Python application only listens to the signal file created by Hammerspoon.

1.  **PortAudio (for `sounddevice`)**
    If you see audio-related errors, install PortAudio:
    ```bash
    brew install portaudio
    pip install --force-reinstall sounddevice
    ```

2.  **Microphone Permissions**
    Make sure your terminal (or app wrapper) has access:
    * System Settings → Privacy & Security → Microphone.

---

## 🪟 Windows Notes

1.  **Python & Tkinter**
    Install Python from `python.org` and check **“Add Python to PATH”**. Tkinter is included by default.

2.  **Microphone Permissions**
    On recent Windows: Settings → Privacy & security → Microphone. Enable access for desktop apps.

3.  **Global Hotkey**
    The hotkey is **`Ctrl + Alt + F9`** and is handled by the included `pynput` dependency.

---

## 🐧 Linux Notes

1.  **System Packages (Debian/Ubuntu)**
    Install required packages for audio and GUI:
    ```bash
    sudo apt update
    sudo apt install -y python3 python3-venv python3-tk \
                           libportaudio2 libsndfile1
    ```

2.  **Global Hotkey**
    The hotkey is **`Ctrl + Alt + F9`** and is handled by `pynput`. If your desktop environment intercepts this shortcut, rely on the in-window hotkey.

---

## ❓ FAQ

**Q: Does Dictaria work offline?**

A: Yes. After the model is downloaded the first time, transcription is local.

**Q: Can I use a different model (small, large-v3)?**

A: Yes. In `dictaria.py`, change `MODEL_SIZE = "medium"`.

**Q: How do I reset languages?**

A: Close Dictaria and delete `~/.dictaria_config.json`.

---

## Credits

* Core transcription technology provided by [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
* **macOS Hotkey solution via File Polling inspired by the Hammerspoon community.**
* Vibe-coded with assistance from Google's Gemini models and ChatGPT (GPT-5.1 Thinking).

## License

This project is licensed under the MIT License.

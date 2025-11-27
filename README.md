<p align="center">
  <img src="icon.png" alt="Dictaria icon" width="180">
</p>

# Dictaria 🎤 - Local Speech-to-Text Tool

Dictaria is a small desktop dictation app.

It listens to your microphone, transcribes audio locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and dumps everything into a simple multi-language text window with a global hotkey.

> VIBE-CODED with ChatGPT (GPT-5.1 Thinking)

---

## ✨ Features

* Records from the system default microphone.
* Local transcription with `faster-whisper` (`medium` model by default).
* **Automatically copies transcribed text to the system clipboard (portapapeles).**
* Multi-language support:
    * Whisper supports many languages.
    * Dictaria’s UI exposes 10 common ones by default: Spanish, English, Japanese, French, German, Italian, Portuguese, Chinese, Russian, Korean.
* Favorite languages bar (up to 5 favorites) with emoji flags.
* Global hotkey:
    * macOS: `Cmd + Shift + J`
    * Windows / Linux: `Ctrl + Shift + J`
* Simple UI:
    * Circular red button to start/stop recording.
    * Scrollable text area with all transcriptions.
    * Status messages in English: `[Listening...]`, `[Transcribing...]`, etc.
* Persistent config in `~/.dictaria_config.json`:
    * Favorite languages.
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
* `pynput`

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

    # Windows (CMD)
    .venv\Scripts\activate.bat
    ```

3.  Install dependencies:

    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

4.  Run Dictaria:

    ```bash
    python dictaria.py
    ```

> On first launch, faster-whisper will download and load the medium model. This can take a bit of time.

---

## ▶️ How to Use

1.  **Start Dictaria:**
    ```bash
    cd dictaria
    source .venv/bin/activate   # or the Windows equivalent
    python dictaria.py
    ```

2.  Select your favorite languages in the **Languages ▾** menu and click a flag to set it as the active language.

3.  **Start dictation** by clicking the red button or pressing the global hotkey:
    * macOS: `Cmd + Shift + J`
    * Windows / Linux: `Ctrl + Shift + J`

4.  Press the hotkey again (or click the button) to stop recording and start transcription. **Once transcription is complete, the resulting text will automatically be copied to your clipboard (portapapeles).**

---

## 💻 Configuration

Dictaria stores a tiny JSON file in your home directory: `~/.dictaria_config.json`.

* Change favorites in the **Languages ▾** menu.
* Click flags to change the active language.
* Delete `~/.dictaria_config.json` if you want to reset everything.

---

## 🍏 macOS Notes

1.  **PortAudio (for `sounddevice`)**
    If you see audio-related errors, install PortAudio:
    ```bash
    brew install portaudio
    pip install --force-reinstall sounddevice
    ```

2.  **Microphone Permissions**
    Make sure your terminal (or app wrapper) has access:
    * System Settings → Privacy & Security → Microphone.

3.  **Accessibility Permissions (Global Hotkey)**
    The global hotkey requires accessibility / input monitoring permissions:
    * System Settings → Privacy & Security → Accessibility.
    * Add your terminal (and/or your Dictaria `.app` wrapper) and enable "Allow this app to control your computer".

---

## 🪟 Windows Notes

1.  **Python & Tkinter**
    Install Python from `python.org` and check **“Add Python to PATH”**. Tkinter is included by default.

2.  **Microphone Permissions**
    On recent Windows: Settings → Privacy & security → Microphone. Enable access for desktop apps.

3.  **Global Hotkey**
    The hotkey is `Ctrl + Shift + J`. If it fails globally, use the in-window hotkey (same combo while Dictaria is focused).

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
    The hotkey is `Ctrl + Shift + J`. If your desktop environment intercepts this shortcut, rely on the in-window hotkey.

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
* Vibe-coded with assistance from Google's Gemini models and ChatGPT (GPT-5.1 Thinking).

## License

This project is licensed under the MIT License.

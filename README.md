
<p align="center">
  <img src="icon.png" alt="Dictaria icon" width="180">
</p>

# Dictaria

Dictaria is a small desktop dictation app.

It listens to your microphone, transcribes audio locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and dumps everything into a simple multi-language text window with a global hotkey.

> VIBE-CODED with ChatGPT (GPT-5.1 Thinking) and Gemini.

---

## Features

* Records from the system default microphone.
* Local transcription with `faster-whisper` (`medium` model by default).
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

## Requirements

### Common

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

---

## Quick install (all platforms)

1.  Clone the repository:

    bash
    git clone [https://github.com/dnlcstr/dictaria.git](https://github.com/dnlcstr/dictaria.git)
    cd dictaria
    

2.  Create and activate a virtual environment (recommended):

    bash
    python -m venv .venv

    # macOS / Linux
    source .venv/bin/activate

    # Windows (PowerShell)
    .venv\Scripts\Activate.ps1

    # Windows (CMD)
    .venv\Scripts\activate.bat
    

3.  Install dependencies:

    bash
    pip install --upgrade pip
    pip install -r requirements.txt
    

4.  Run Dictaria:

    bash
    python dictaria.py
    

> On first launch, faster-whisper will download and load the medium model. This can take a bit of time. You should see messages like:
>
> `[Initializing Dictaria Model... please wait]`
> `[Dictaria Ready. Press Cmd + Shift + J to dictate]`
> (or `Ctrl + Shift + J` on Windows / Linux).

---

## How to use

1.  **Start Dictaria:**
    bash
    cd dictaria
    source .venv/bin/activate   # or the Windows equivalent
    python dictaria.py
    

2.  In the top bar, open **Languages ▾** and select your favorite languages (you can have up to 5). Your favorites appear as flags above the red button. Click a flag to set it as the active language.

3.  **Start dictation** in any of these ways:
    * Click the red circular button.
    * Press the global hotkey:
        * macOS: `Cmd + Shift + J`
        * Windows / Linux: `Ctrl + Shift + J`
    * Or, if the global hotkey is not working, use the same combo while the Dictaria window is focused.

4.  **While recording:**
    * Status line shows `[Listening...]`.
    * Press the hotkey again (or click the button again) to stop.

5.  **After stopping:**
    * Status shows `[Transcribing...]`.
    * The recognized text is appended to the text box.
    * If audio was too short or silent, you’ll see `[Audio too short or silent]`.

> You can scroll, select, copy and paste from the text area freely.

---

## Configuration

Dictaria stores a tiny JSON file in your home directory: `~/.dictaria_config.json`

It contains for example:
json
{
  "favorites": ["es", "en", "ja"],
  "active": "es"
}
`

  * `favorites`: list of language codes you picked in the menu.
  * `active`: the currently active language (also reflected by the highlighted flag).

You can:

  * Change favorites in the **Languages ▾** menu.
  * Click flags to change the active language.
  * Delete `~/.dictaria_config.json` if you want to reset everything.

-----

## macOS notes

1.  **Tkinter**

    If you installed Python via:

      * the official installer from `python.org`, or
      * Homebrew (`brew install python`)

    Tkinter usually comes bundled. If you get errors that mention `Tk` or `tkinter`, re-install Python from `python.org` or ensure `python-tk/tk` is installed for your specific Python build.

2.  **PortAudio (for `sounddevice`)**

    Normally the wheel includes what you need, but if you see audio-related errors, install PortAudio:

    bash
    brew install portaudio
    pip install --force-reinstall sounddevice
    

3.  **Microphone permissions**

    Make sure your terminal (or app wrapper) has access to the microphone:

      * System Settings → Privacy & Security → Microphone.
      * Enable access for Terminal / iTerm / your preferred terminal.

4.  **Accessibility permissions (global hotkey)**

    The global hotkey uses `pynput`, which requires accessibility / input monitoring permissions on macOS:

      * System Settings → Privacy & Security → Accessibility.
      * Add your terminal (and/or your Dictaria `.app` wrapper if you create one).
      * Enable “Allow this app to control your computer”.

    If not granted:

      * The global hotkey won’t work.
      * The in-window hotkey (`Cmd + Shift + J` with Dictaria focused) still works.

5.  **Optional: Automator `.app` wrapper**

    You can create a clickable app icon using Automator:

      * Open Automator → create a new **Application**.
      * Add a **Run Shell Script** action.
      * Use something like:
        bash
        cd /Users/your-user/Documents/python_projects/dictaria
        source .venv/bin/activate
        python dictaria.py
        
      * Save as `Dictaria.app`.
      * Give it microphone and accessibility permissions if you want to use the global hotkey.

    > Put your `icon.png` in the same directory as `dictaria.py` so Tk can use it as a window icon.

-----

## Windows notes

1.  **Python & Tkinter**

    Install Python from `python.org`:

      * Check **“Add Python to PATH”** during installation.
      * Tkinter is included by default.

2.  **Dependencies**

    Inside the virtual environment: `pip install -r requirements.txt`

      * If you see build errors with any package, make sure you are using a supported Python version (3.10+).

3.  **Microphone permissions**

    On recent Windows:

      * Settings → Privacy & security → Microphone.
      * Enable “Microphone access”.
      * Enable “Let desktop apps access your microphone”.

    Then run Dictaria again from a terminal.

4.  **Global hotkey**

    On Windows the global hotkey is: `Ctrl + Shift + J`.
    If another app grabs that combo or your system blocks low-level hooks, you may see an error in the console and the global hotkey won’t fire. You can always fall back to the in-window hotkey.

-----

## Linux notes

Linux is more fragmented, but the typical setup on Debian/Ubuntu-like systems is:

1.  **System packages**

    bash
    sudo apt update
    sudo apt install -y python3 python3-venv python3-tk \
                        libportaudio2 libsndfile1
    

      * `python3-tk` → Tkinter.
      * `libportaudio2` → required by `sounddevice`.
      * `libsndfile1` → required by `soundfile`.

    Then follow the installation steps (clone, venv, `pip install`).

2.  **Fonts / emoji flags**

    The app tries to use emoji fonts for the language flags and falls back to a generic Sans font on Linux. If your desktop does not have a color emoji font installed, you’ll still see language markers, but flags may look like monochrome glyphs.

3.  **Global hotkey**

    On Linux the hotkey is: `Ctrl + Shift + J`. Some desktop environments may intercept this shortcut for their own shortcuts. If you don’t see the `Global hotkey ... pressed.` message in your terminal when pressing it, either:

      * Choose another combination in the code, or
      * Rely on the in-window hotkey (same combo, but with Dictaria focused).

-----

## FAQ

**Q: Does Dictaria work offline?**
A: After the model is downloaded the first time, transcription is local. No audio is sent anywhere by this script.

**Q: Can I use a different model (small, large-v3)?**
A: Yes. In `dictaria.py`, change:
`MODEL_SIZE = "medium" # "small", "medium", "large-v3"`
Larger models use more RAM/VRAM and are slower, especially on CPU.

**Q: How do I reset languages and favorites?**
A: Close Dictaria and delete `~/.dictaria_config.json`. Next launch will start with no favorites.

-----

## License

Choose a license you prefer (for example MIT):


MIT License
Copyright (c) 2025 YOUR NAME
(Replace this section with the full text of your actual license.)


txt
# requirements.txt

faster-whisper
sounddevice
soundfile
numpy
pynput

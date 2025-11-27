<p align="center">
  <img src="icon.png" alt="Dictaria icon" width="180">
</p>

# Dictaria 🎤 - Local Speech-to-Text Tool

Dictaria is a small desktop dictation app. Its **compact design** keeps it out of your way while you work.

It listens to your microphone, transcribes audio locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and dumps everything into a simple multi-language text window with a global hotkey.

---

## ✨ Features

* Records from the system default microphone.
* Local transcription with `faster-whisper`. It uses the **Whisper v3 medium model** by default, which offers excellent accuracy.
* **Automatically copies transcribed text to the system clipboard (clipboard).**
* **Pin button** 📌 to keep the window **always on top** (foreground).
* **View Collapse Button ⬇️/⬆️:** Allows you to **hide the text area** and minimize the window to a small, non-intrusive strip containing only the language selector and the record button.
* Multi-language support via a single dropdown:
    * Dictaria’s UI exposes 10 common ones by default: Spanish, English, Japanese, French, German, Italian, Portuguese, Chinese, Russian, Korean.
* Global and In-Window hotkeys (see table below).
* Simple UI:
    * **Compact and minimalist window size.**
    * Circular red button to start/stop recording.
    * Scrollable text area with all transcriptions.
    * Status messages in English: `[Listening...]`, `[Transcribing...]`, etc.
* Persistent config in `~/.dictaria_config.json`:
    * Last active language.

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

> Tkinter is usually bundled with the standard Python installers on macOS and Windows. On many Linux distros you must install the `tk` package from your system package manager (see below).

### Quick Install (All Platforms)

1. Clone the repository:

```bash
git clone [https://github.com/dnlcstr/dictaria.git](https://github.com/dnlcstr/dictaria.git)
cd dictaria

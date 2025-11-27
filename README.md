
<p align="center">
  <img src="icon.png" alt="Dictaria icon" width="180">
</p>

# Dictaria 🎤 - Local Speech-to-Text Tool Powered by Faster Whisper

Dictaria is a small, cross-platform desktop tool designed for multi-language speech-to-text transcription. It runs entirely **locally** on your machine, ensuring privacy and speed.

It leverages the power of **`faster-whisper`** for high-performance transcription and provides a minimalist, distraction-free GUI built with Tkinter.

## ✨ Features

- **Local Processing:** All speech-to-text processing happens instantly on your machine (CPU or GPU).
- **High Performance:** Uses `faster-whisper` for efficient inference.
- **Multi-Language Support:** Whisper supports many languages; Dictaria's UI exposes **10 common ones** by default (Spanish, English, Japanese, French, German, Italian, Portuguese, Chinese, Russian, Korean).
- **Favorites:** Select up to **5 favorite languages** displayed as clickable flag icons.
- **Global Hotkey:** Use a convenient hotkey (`Ctrl/Cmd + Shift + J`) to toggle recording from any application.
- **Minimalist GUI:** Dark-themed, distraction-free interface built with native Tkinter.
- **Configuration Persistence:** Remembers your favorite languages, active language, and theme using a simple JSON config file.

---

## 🛠️ Installation and Setup

Dictaria requires **Python 3.10+** (**3.11+ recommended**). The core dependency for audio handling is `sounddevice`, which requires the **PortAudio** library to be installed on your system.

### 1. Clone the Repository

bash
git clone [https://github.com/YOUR_USER/dictaria.git](https://github.com/YOUR_USER/dictaria.git)
cd dictaria
`

### 2\. Create a Virtual Environment (Recommended)

This step isolates Dictaria's dependencies from your system Python.

bash
python3 -m venv .venv
# Activate on macOS/Linux
source .venv/bin/activate
# Activate on Windows (Command Prompt)
# .venv\Scripts\activate.bat


### 3\. Install System Audio Dependencies (PortAudio)

You must install the system library **PortAudio** before installing the Python dependencies.

#### 🍏 macOS

Use Homebrew to install PortAudio:

bash
brew install portaudio


#### 💻 Windows

No specific system-level installation is typically required. The Python package installer (`pip`) usually handles necessary DLLs for `sounddevice` on Windows.

#### 🐧 Linux (Debian/Ubuntu)

Use your distribution's package manager (e.g., `apt`) to install PortAudio development headers:

bash
sudo apt update
sudo apt install libportaudio2 libportaudio-dev


### 4\. Install Python Dependencies

Install the required Python libraries using the `requirements.txt` provided:

bash
pip install -r requirements.txt


**Contents of `requirements.txt`:**

  - `faster-whisper`
  - `sounddevice`
  - `soundfile`
  - `numpy`
  - `pynput`

-----

## 🔒 5. macOS Permissions (Crucial for Hotkey & Audio)

On macOS, the operating system restricts access to the microphone and global keyboard functions for security reasons. You must grant permissions for Dictaria to function fully.

### 🎙️ Microphone Permission

If recording doesn't work (no sound input):

1.  Go to **System Settings** → **Privacy & Security** → **Microphone**.
2.  Ensure that **Terminal** (or your Dictaria application launcher) is checked and has access.

### ⌨️ Accessibility / Input Monitoring (For Global Hotkey)

If the global hotkey (`Cmd + Shift + J`) doesn't work when the app is in the background:

1.  Go to **System Settings** → **Privacy & Security** → **Input Monitoring** or **Accessibility**.
2.  If you see a warning like: `This process is not trusted! Input event monitoring will not be possible...`, you must manually add and enable the **Terminal** (or your Dictaria application launcher) to this list.

-----

## ▶️ Running Dictaria

From the project folder, with your virtual environment activated:

bash
python dictaria.py


### Global Hotkey

The global hotkey toggles recording on and off from any running application.

| OS | Key Combination | Hotkey Label |
| :--- | :--- | :--- |
| **macOS** | `Command + Shift + J` | `Cmd + Shift + J` |
| **Windows/Linux** | `Control + Shift + J` | `Ctrl + Shift + J` |

-----

## ⚙️ Model Configuration

The core model settings are defined at the top of the `dictaria.py` script:

python
MODEL_SIZE = "medium"       # "small", "medium", "large-v3"
DEVICE = "cpu"              # Change to "cuda" if you have an NVIDIA GPU
COMPUTE_TYPE = "int8"       # "int8" is faster/lighter on CPU


  - **`MODEL_SIZE`:** You can change this to `small` (faster, less accurate) or `large-v3` (slower, more accurate). The model will be downloaded upon first launch.
  - **`DEVICE`:** Processing defaults to **CPU**. If you have an NVIDIA GPU, you can change the value to `"cuda"` for significant acceleration (requires proper CUDA and PyTorch setup).

-----

## 📜 Credits and License

  - Core transcription technology provided by [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
  - Vibe-coded with assistance from Google's Gemini models.

This project is licensed under the **MIT License**.
See the LICENSE file for details.

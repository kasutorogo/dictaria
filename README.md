# Dictaria

Dictaria is a small local desktop tool for multi-language speech-to-text. 
It uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), `sounddevice`, and a minimalist Tkinter GUI.

You select up to five favorite languages, pick one flag, and then use a global hotkey to start and stop recording from your microphone. Transcription is done locally on your machine.

## Features

- Local speech-to-text using `faster-whisper`
- Multiple languages selectable from a menu
- Up to 5 favorite languages with flag icons
- Clickable favorites row above the record button
- Global hotkey: `Cmd + Shift + J` (on macOS, or Win + Shift + J on a PC keyboard)
- Dark mode and light mode toggle (☾ / ☀︎)
- Minimal, distraction-free GUI in Tkinter
- System messages in English, transcribed text in the selected language
- Simple JSON config file to remember favorites, last language, theme and help panel visibility

## How it works

Dictaria is a single Python script that:

1. Loads a `faster-whisper` model (by default `medium`) on CPU.
2. Opens a Tkinter window with:
 - Top bar with app name, instructions, theme toggle and language menu
 - A favorites row showing up to five language flags
 - A round red record button
 - A scrollable text area for transcription output
3. Listens to your microphone using `sounddevice` and records audio chunks.
4. After you stop recording, it writes the audio to a temporary `.wav` file.
5. Uses `WhisperModel.transcribe()` from `faster-whisper` with the selected language code.
6. Appends the recognized text to the text box.

All speech-to-text processing happens locally.

## Installation (macOS)

### 1. Clone the repository

bash
git clone https://github.com/YOUR_USER/dictaria.git
cd dictaria

2. (Recommended) Create and activate a virtual environment

python3 -m venv .venv
source .venv/bin/activate

3. Install system dependency for audio (PortAudio)

Using Homebrew:

brew install portaudio

4. Install Python dependencies

pip install -r requirements.txt

This will install:
 - faster-whisper
 - sounddevice
 - soundfile
 - numpy
 - pynput

Running Dictaria

From the project folder:

# (activate the venv if you use one)
source .venv/bin/activate # on macOS / Linux

python dictaria.py

Dictaria will open a window with:
 - A top bar (title, instructions, theme toggle, language menu)
 - A favorites row (empty at first)
 - A round red record button (disabled until you choose a language)
 - A scrollable text box for transcriptions
 - An optional help panel at the bottom

Global hotkey
 - Default hotkey: Cmd + Shift + J
 - Behavior:
 - If there is an active language, the hotkey toggles recording on and off.
 - If no language is selected, Dictaria prints a small red system message asking you to choose a language first.

The hotkey is implemented using pynput.keyboard.GlobalHotKeys.
Dictaria must be running for the hotkey to work.

On a Windows keyboard connected to macOS, use the “Win” key where Cmd is expected.

Languages

The script defines a set of languages with:
 - Whisper language code
 - Flag emoji
 - Native name

Example entries:
 - es · 🇪🇸 Español
 - en · 🇬🇧 English
 - ja · 🇯🇵 日本語
 - pt · 🇵🇹 Português
 - fr · 🇫🇷 Français
 - de · 🇩🇪 Deutsch
 - ru · 🇷🇺 Русский
 - he · 🇮🇱 עברית
 - ar · 🇸🇦 العربية
 - zh · 🇨🇳 中文
 - ko · 🇰🇷 한국어
 - pl · 🇵🇱 Polski
 - uk · 🇺🇦 Українська
 - and several more common languages

You can select as many languages as you want in the dropdown menu, but only 5 can be marked as favorites at the same time.

Favorites and active language
 - At the top of the main card there is a favorites row.
 - Favorites are chosen from the language dropdown menu (check the flags you want).
 - Each favorite appears as a flag pill above the record button.
 - Clicking on a favorite flag sets that language as the active language.
 - The active language:
 - Controls which language code is passed to faster-whisper.
 - Controls which flag is visually highlighted.
 - Enables the red record button.

If there is no active language, the record button stays grey and cannot be used.

Theme and system messages
 - Dictaria starts in dark mode by default.
 - You can toggle dark/light mode with the ☾ / ☀︎ button in the top bar.
 - The choice of theme is saved in a small JSON config file in your home directory.

System messages always appear:
 - In English
 - In red
 - In a slightly smaller font
 - Inside the main text box, tagged as system

Examples:
 - [Please choose a language before recording]
 - [Listening / Escuchando...]
 - [Transcribing / Transcribiendo (en)...]
 - [No useful audio recorded]
 - [No text recognized]
 - [Favorites limit reached (5)]

Your actual dictated text is inserted in the normal font and color (white in dark mode, black in light mode).

Config file

Dictaria stores a small JSON configuration file in your home directory, for example:

{
 "theme": "dark",
 "favorites": ["es", "en", "ja"],
 "active_language": "es",
 "show_help": false
}

It updates automatically when you:
 - Change favorites
 - Change the active language
 - Toggle dark/light mode
 - Show or hide the help panel

Optional: macOS launcher (Automator)

If you want to launch Dictaria like a normal app, you can create a small .app with Automator that runs:

cd /path/to/dictaria
source .venv/bin/activate
python dictaria.py

This is optional and specific to your setup; the recommended way to run Dictaria is directly via python dictaria.py from the project folder.

Requirements

Python packages (minimum):
 - faster-whisper
 - sounddevice
 - soundfile
 - numpy
 - pynput

Standard library:
 - tkinter
 - threading
 - queue
 - tempfile
 - json
 - os

On macOS you may also need:
 - PortAudio installed via Homebrew:
 - brew install portaudio

Credits

Vibe-coded with ChatGPT (GPT-5.1 Thinking).

License

This project is licensed under the MIT License.
See the LICENSE file for details.

text
# requirements.txt
faster-whisper
sounddevice
soundfile
numpy
pynput

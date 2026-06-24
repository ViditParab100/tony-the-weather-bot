# Tony — Voice AI Assistant

Tony is a local, always-listening voice assistant built in Python. It listens through your microphone, thinks using a cloud LLM, and speaks back using an on-device TTS engine. It can also search the web and open URLs on command.

## How It Works

```
You speak → ears.py (Sarvam STT) → brain.py (Sarvam LLM) → mouth.py (Kokoro TTS) → You hear
                                         ↓ if needed
                                     tools.py (DuckDuckGo / browser)
```

Tony pauses the microphone while it's speaking to prevent echo feedback.

## Stack

| Layer | Technology |
|-------|-----------|
| Speech-to-Text | Sarvam AI `saaras:v3` (en-IN) |
| LLM | Sarvam AI `sarvam-30b` |
| Text-to-Speech | Kokoro ONNX (local, offline) — `am_adam` voice |
| Web Search | DuckDuckGo (`ddgs`) |
| Mic capture | `speech_recognition` + `sounddevice` |

## Project Structure

```
tony-the-weather-bot/
├── main.py          # Entry point — listen → think → speak loop
├── brain.py         # LLM via Sarvam AI, maintains chat history
├── ears.py          # Speech-to-text via Sarvam AI
├── mouth.py         # Text-to-speech via Kokoro ONNX (runs on a thread)
├── tools.py         # Web search (DuckDuckGo) + open URL in browser
├── config.py        # API key + location config
├── voice-agent.py   # Earlier monolithic prototype (Whisper STT + Sarvam TTS)
├── kokoro-v0_19.onnx   # Kokoro TTS model weights
└── voices-v1.0.bin     # Kokoro voice pack
```

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/ViditParab100/tony-the-weather-bot.git
cd tony-the-weather-bot
```

**2. Create a virtual environment and install dependencies**
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS / Linux

pip install sarvamai speechrecognition sounddevice kokoro-onnx ddgs
```

**3. Download the Kokoro model files**

Place these two files in the project root:
- `kokoro-v0_19.onnx`
- `voices-v1.0.bin`

**4. Set your Sarvam API key**
```bash
# Windows (PowerShell)
$env:SARVAM_API_KEY = "your_key_here"

# macOS / Linux
export SARVAM_API_KEY="your_key_here"
```

**5. (Optional) Set your location**

Edit `config.py` to change the default location (used by the LLM for context):
```python
LOCATION = "Bengaluru"
```

**6. Run**
```bash
python main.py
```

## Agent Capabilities

Tony uses a simple tag-based tool protocol embedded in LLM responses:

- `SEARCH[query]` — triggers a DuckDuckGo search and summarizes the results
- `OPEN_TAB[url]` — opens a URL in the default browser

Example interactions:
- *"What's the weather in Bengaluru?"* → Tony searches and summarizes
- *"Open YouTube"* → Tony opens `youtube.com`
- *"What's 2 + 2?"* → Tony answers directly (no search needed)

## Notes

- Tony responds in **one sentence by default**. Ask for "detail" or "explanation" to get longer answers.
- The mic is muted while Tony is speaking to avoid self-triggering.
- `voice-agent.py` is an older prototype that used faster-whisper for STT and Sarvam for TTS — kept for reference.

# Tony — Voice AI Assistant

Tony is a local, always-listening voice assistant for Windows. It listens through your microphone, thinks with a cloud LLM, speaks with an on-device TTS engine, and can control apps, tabs, and place orders on Blinkit and Zomato.

## Architecture

```
You speak → ears.py (Sarvam STT) → brain.py (Groq LLM) → mouth.py (Kokoro TTS) → You hear
                                         ↓ if needed
                                     tools.py     — web search, app/tab control, system time, weather
                                     blinkit.py   — Playwright browser automation (Blinkit)
                                     zomato.py    — Playwright browser automation (Zomato)
```

## Stack

| Layer | Technology |
|-------|------------|
| Speech-to-Text | Sarvam AI `saaras:v3` (en-IN) |
| LLM | Groq `llama-3.1-8b-instant` (primary) / Sarvam `sarvam-30b` (fallback) |
| Text-to-Speech | Kokoro ONNX (local, offline) — `am_onyx` voice |
| Web Search | DuckDuckGo (`ddgs`) + wttr.in (weather) |
| Grocery ordering | Playwright + Blinkit |
| Food ordering | Playwright + Zomato |
| Mic capture | `speech_recognition` (listen_in_background) |

## Project Structure

```
tony-the-weather-bot/
├── main.py          # Entry point — listen → think → speak loop
├── brain.py         # LLM interface (Groq / Sarvam), chat history, system prompt
├── ears.py          # Speech-to-text via Sarvam saaras:v3
├── mouth.py         # Text-to-speech via Kokoro ONNX (pipelined synth + playback)
├── tools.py         # Web search, weather, app/tab/browser control, code execution
├── blinkit.py       # Blinkit grocery ordering via Playwright
├── zomato.py        # Zomato food ordering via Playwright
├── config.py        # API keys + location config
├── test_tony.py     # Text-mode test runner (interactive or batch)
├── queries.txt      # Sample test queries
├── kokoro-v0_19.onnx   # Kokoro TTS model weights (not in git)
└── voices-v1.0.bin     # Kokoro voice pack (not in git)
```

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/ViditParab100/tony-the-weather-bot.git
cd tony-the-weather-bot
```

**2. Create a virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
```

**3. Install dependencies**
```bash
pip install sarvamai groq speechrecognition sounddevice kokoro-onnx ddgs \
            requests python-dotenv colorama pygetwindow pyautogui playwright
playwright install firefox
```

**4. Download Kokoro model files**

Place these in the project root (not tracked by git):
- `kokoro-v0_19.onnx`
- `voices-v1.0.bin`

Download from the [Kokoro ONNX releases](https://github.com/thewh1teagle/kokoro-onnx/releases).

**5. Add API keys**

Create a `.env` file in the project root:
```
SARVAM_API_KEY=your_sarvam_key
GROQ_API_KEY=your_groq_key
```

Get keys from [console.groq.com](https://console.groq.com) (free, 500k tokens/day) and [console.sarvam.ai](https://console.sarvam.ai).

**6. Set your location** (optional)

Edit `config.py`:
```python
LOCATION = "Bengaluru"
```

**7. Run**
```bash
python main.py
```

---

## Capabilities

### Conversation
- Answers general knowledge questions from memory
- Dry wit; serious on sensitive topics
- One-sentence replies by default

### Web & Search
| What you say | What happens |
|---|---|
| "What's the weather in Bengaluru?" | Fetches wttr.in, speaks temp + conditions |
| "What time is it?" | Reads system clock instantly (no internet) |
| "Who won IPL 2024?" | DuckDuckGo search + LLM summary |
| "Google it" / "Search on Google" | Opens Google search in browser |

### App Control
| What you say | What happens |
|---|---|
| "Open Spotify" | Launches the app |
| "Close Notepad" | Kills the process |
| "Open YouTube" | Opens in default browser |
| "Open Zomato.com" | Opens `https://zomato.com` directly |

### Browser & Tab Control
| What you say | Token |
|---|---|
| "Close this tab" | `CLOSE_TAB` |
| "New tab" | `NEW_TAB` |
| "Next tab" | `NEXT_TAB` |
| "Previous tab" | `PREV_TAB` |
| "Reopen closed tab" | `REOPEN_TAB` |
| "Scroll down" | `SCROLL_DOWN` |
| "Scroll up" | `SCROLL_UP` |
| "Press Enter" | `PRESS_KEY[enter]` |

### Code
| What you say | What happens |
|---|---|
| "Write a Python function to sort a list" | Tony writes the code |
| "Run it" | Executes in a sandboxed temp file (10s timeout) |
| "Open it in VS Code" | Opens the temp file in VS Code |

### Blinkit (Grocery Ordering)
See [Blinkit setup](#blinkit-setup) below.

| What you say | What happens |
|---|---|
| "Blinkit login" | Opens browser for one-time login |
| "Order milk from Blinkit" | Searches milk, adds first result to cart |
| "Add 2 packs of bread to Blinkit" | Adds 2× bread to cart |
| "What's in my Blinkit cart?" | Opens Blinkit and reads cart |

### Zomato (Food Ordering)
See [Zomato setup](#zomato-setup) below.

| What you say | What happens |
|---|---|
| "Zomato login" | Opens browser for one-time login |
| "Order butter chicken on Zomato" | Searches dish, opens first restaurant, adds to cart |
| "Order pizza from Domino's on Zomato" | Opens Domino's specifically, adds pizza |
| "What's in my Zomato cart?" | Opens Zomato cart and reads contents |

### Safety Guardrails
- Will not delete files, modify the filesystem, or run shell commands
- Will not shut down, restart, or hibernate Windows
- Protected system processes (lsass, csrss, svchost, etc.) cannot be killed
- Shell injection in app names is blocked
- Code execution runs in a sandboxed temp file with a 10-second timeout

### Interruption Handling
- Say something while Tony is speaking to interrupt
- Tony answers your new question first, then asks if you want it to continue
- If Tony is already handling 2 queued questions while speaking, further complex questions are dropped (simple actions like open/close/scroll still go through)

### Shutdown
Say "shut down Tony", "bye Tony", or "sleep Tony". Tony will ask for confirmation before exiting.

---

## Blinkit Setup

Blinkit automation uses Playwright (Firefox) with a persistent profile stored at `~/.tony/blinkit_profile`. You log in once; the session is saved forever.

**Steps:**

1. Say **"Tony, Blinkit login"**
2. A Firefox window opens at blinkit.com
3. Enter your **phone number** and tap Continue
4. Enter the **OTP** received on your phone
5. Once logged in, Tony says *"Logged in to Blinkit. Session saved."*
6. The browser closes. You're done — no login needed again.

**Ordering:**
- Say *"Order milk from Blinkit"* — Firefox opens, searches milk, clicks Add, leaves browser open
- Review the cart in the browser and tap **Proceed to Pay** yourself
- Tony never touches the payment step

**Notes:**
- The cart is stored on Blinkit's servers (tied to your account). If the browser closes, you can still open blinkit.com in Chrome and see your cart.
- If the session expires, just say "Blinkit login" again.

---

## Zomato Setup

Zomato automation works the same way — persistent Firefox profile at `~/.tony/zomato_profile`.

**Steps:**

1. Say **"Tony, Zomato login"**
2. A Firefox window opens at zomato.com
3. Click **Log In**, enter your **phone number**, then the **OTP**
4. Once logged in, Tony says *"Logged in to Zomato. Session saved."*
5. The browser closes. Done.

**Ordering:**
- Say *"Order butter chicken on Zomato"* — Firefox opens, searches the dish, opens the first matching restaurant, clicks Add
- To target a specific restaurant: *"Order pizza from Domino's on Zomato"*
- Review the cart in the browser and place the order yourself

**Notes:**
- If a customisation popup appears (e.g. spice level), Tony clicks through automatically
- If the browser selectors change after a Zomato update, share the console error and the selectors will be patched

---

## Testing

Run in interactive text mode (no mic needed):
```bash
python test_tony.py
```

Run a batch of queries with expected output assertions:
```bash
python test_tony.py --batch queries.txt
```

---

## Switching LLM

Edit `config.py`:
```python
LLM_PROVIDER = "groq"    # fast, 500k tokens/day free
# LLM_PROVIDER = "sarvam"  # fallback
```

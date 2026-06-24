# Tony — Voice AI Assistant

Tony is a local, always-listening voice assistant for Windows. It listens through your microphone, thinks with a cloud LLM, speaks with an on-device TTS engine, and can control apps, tabs, place grocery orders on Blinkit, and order food on Zomato.

## Architecture

```
You speak → ears.py (Sarvam STT) → brain.py (Groq LLM) → mouth.py (Kokoro TTS) → You hear
                                         ↓ if needed
                                     tools.py     — web search, app/tab/window control, system time, weather
                                     blinkit.py   — Playwright browser automation (Blinkit grocery)
                                     zomato.py    — Playwright browser automation (Zomato food)
```

## Stack

| Layer | Technology |
|-------|------------|
| Speech-to-Text | Sarvam AI `saaras:v3` (en-IN) |
| LLM | Groq `llama-3.1-8b-instant` (primary) / Sarvam `sarvam-30b` (fallback) |
| Text-to-Speech | Kokoro ONNX (local, offline) — `am_onyx` voice |
| Web Search | DuckDuckGo (`ddgs`) + wttr.in (weather) |
| Grocery ordering | Playwright + Firefox (Blinkit) |
| Food ordering | Playwright + Firefox (Zomato) |
| Mic capture | `speech_recognition` (listen_in_background) |

## Project Structure

```
tony-the-weather-bot/
├── main.py          # Entry point — listen → think → speak loop
├── brain.py         # LLM interface (Groq / Sarvam), chat history, system prompt
├── ears.py          # Speech-to-text via Sarvam saaras:v3
├── mouth.py         # Text-to-speech via Kokoro ONNX (pipelined synth + playback)
├── tools.py         # Web search, weather, app/tab/window control, code execution
├── blinkit.py       # Blinkit grocery ordering via Playwright
├── zomato.py        # Zomato food ordering via Playwright
├── config.py        # API keys + location config
├── test_tony.py     # Text-mode test runner (interactive or batch)
├── test_blinkit.py  # Blinkit end-to-end test suite (Pay Now mocked)
├── test_zomato.py   # Zomato automation test suite
├── queries.txt      # Sample test queries for test_tony.py
├── kokoro-v0_19.onnx   # Kokoro TTS model weights (not in git — download separately)
└── voices-v1.0.bin     # Kokoro voice pack (not in git — download separately)
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

Place these in the project root (gitignored — not tracked):
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
LOCATION  = "Bengaluru"
ZOMATO_CITY = "bangalore"   # city slug used in Zomato URLs
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
| "What time is it?" | Reads system clock instantly (no internet needed) |
| "Who won IPL 2024?" | DuckDuckGo search + LLM summary |
| "Google it" / "Search on Google" | Opens Google search in browser |

### App & Window Control
| What you say | What happens |
|---|---|
| "Open Spotify" | Launches the app |
| "Close Notepad" | Kills the process |
| "Minimize Firefox" | Minimizes the window |
| "Open YouTube" | Opens in default browser |

### Browser & Tab Control
| What you say | Token |
|---|---|
| "Close this tab" | `CLOSE_TAB` |
| "New tab" | `NEW_TAB` |
| "Next tab" | `NEXT_TAB` |
| "Previous tab" | `PREV_TAB` |
| "Reopen closed tab" | `REOPEN_TAB` |
| "Scroll down / up" | `SCROLL_DOWN` / `SCROLL_UP` |
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
| "Order milk from Blinkit" | Searches, adds first result to cart |
| "Add 2 bread to Blinkit" | Adds 2× bread (max 6 per item, 10/day) |
| "Remove milk from Blinkit" | Finds milk in cart, clicks − to remove |
| "Remove 2 milk" | Reduces milk qty by 2 |
| "What's in my Blinkit cart?" | Navigates to checkout, reads item count |
| "Checkout" / "Open cart" | Opens blinkit.com/checkout in browser |
| "Pay now" / "Place order" | Navigates to checkout and asks for confirmation |

> **Context-aware ordering:** When a Blinkit Firefox window is open, Tony automatically treats grocery requests (e.g. "add bread", "get eggs") as Blinkit orders — no need to say "Blinkit" every time.

### Zomato (Food Ordering)
See [Zomato setup](#zomato-setup) below.

| What you say | What happens |
|---|---|
| "Zomato login" | Opens browser for one-time login |
| "Order butter chicken on Zomato" | Searches dish, opens first restaurant, adds to cart |
| "Order pizza from Domino's on Zomato" | Targets a specific restaurant |
| "What's in my Zomato cart?" | Opens Zomato cart |

> **Note:** Zomato's web ordering is periodically blocked by their "mobile app only" banner. If ordering fails, use the Zomato app directly.

---

## Safety Guardrails

- Will not delete files, modify the filesystem, or run shell commands
- Will not shut down, restart, or hibernate Windows
- Protected system processes (`lsass`, `csrss`, `svchost`, etc.) cannot be killed
- Shell injection in app names is blocked
- Code execution runs in a sandboxed temp file with a 10-second timeout
- **Order limits:** max 6 of any single item, max 10 total items per day (resets at midnight)
- **Pay Now requires confirmation:** Tony asks *"Say yes to confirm, or no to cancel"* before placing any order

## Smart Behaviours

### Interruption handling
Say something while Tony is speaking to interrupt. Tony answers the new question first, then asks if you want it to continue the previous thought.

If Tony is already handling 2 queued questions while speaking, further complex questions are silently dropped. Simple actions (open, close, scroll, tab) always go through regardless.

### Shutdown
Say *"shut down Tony"*, *"bye Tony"*, or *"sleep Tony"*. Tony asks for confirmation before exiting.

### System time
*"What time is it?"* reads the local PC clock directly — no internet call, no delay.

---

## Blinkit Setup

Blinkit automation uses Playwright (Firefox) with a persistent profile at `~/.tony/blinkit_profile`. Log in once; the session is saved indefinitely.

**One-time login:**
1. Say **"Tony, Blinkit login"**
2. Firefox opens at blinkit.com
3. Enter your **phone number** → Continue → **OTP**
4. Tony says *"Logged in to Blinkit. Session saved."*

**How ordering works:**
- Tony searches for the item on blinkit.com, clicks **ADD** (or **+** if already in cart), and leaves the browser open
- Say **"checkout"** to open `blinkit.com/checkout`
- Say **"pay now"** → Tony asks *"Say yes to confirm"* → on confirmation, clicks Pay Now

**Notes:**
- Cart is stored server-side — visible in any browser (same Blinkit account)
- If the session expires, say "Blinkit login" again
- ADD buttons on Blinkit are `<div>` elements (not `<button>`), so Tony uses JavaScript to interact with them

---

## Zomato Setup

Zomato automation uses a persistent Firefox profile at `~/.tony/zomato_profile`.

**One-time login:**
1. Say **"Tony, Zomato login"**
2. Firefox opens at zomato.com
3. Click **Log In** → enter phone → OTP
4. Tony says *"Logged in to Zomato. Session saved."*

**How ordering works:**
- Say *"Order butter chicken on Zomato"* — Tony searches, opens the first matching restaurant, clicks Add
- To target a specific restaurant: *"Order pizza from Domino's on Zomato"*
- Review the cart in the browser and place the order yourself

---

## Testing

**Text-mode (no mic needed):**
```bash
python test_tony.py
```

**Batch assertions:**
```bash
python test_tony.py --batch queries.txt
```

**Blinkit end-to-end (browser required, real cart):**
```bash
python test_blinkit.py
```
> Pay Now is mocked in tests — the button is verified as present and visible but never clicked, so no real orders are placed.

---

## Switching LLM

Edit `config.py`:
```python
LLM_PROVIDER = "groq"    # fast, 500k tokens/day free
# LLM_PROVIDER = "sarvam"  # fallback
```

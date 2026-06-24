# main.py
import re
import sys
import json
import threading
import speech_recognition as sr
import queue
import time
from datetime import date
from pathlib import Path
from colorama import init as colorama_init, Fore, Style
colorama_init()
from ears import transcribe_audio
from mouth import speak, is_speaking, stop_speaking, get_last_spoken_text, get_last_speech_end_time
from brain import get_response, summarize_search, store_response
from tools import search_web, is_instant_query, open_url, open_app, close_app, minimize_app, close_tab, new_tab, next_tab, prev_tab, reopen_tab, scroll_down, scroll_up, press_key, save_code, run_code, open_in_vscode, blinkit_is_open, get_foreground_window
from blinkit import blinkit_login, blinkit_add_to_cart, blinkit_remove_from_cart, blinkit_check_cart, blinkit_open_checkout, blinkit_pay_now, parse_blinkit_order, parse_blinkit_remove
from zomato import zomato_login, zomato_order, zomato_check_cart, parse_zomato_order

_C = {
    "brain": Fore.CYAN,
    "think": Fore.YELLOW,
    "tony":  Fore.GREEN,
    "you":   Fore.WHITE,
    "dim":   Fore.LIGHTBLACK_EX,
    "reset": Style.RESET_ALL,
}
def _p(tag, msg, color="reset"):
    print(f"{_C[color]}{tag}{msg}{_C['reset']}")

_CODE_RE = re.compile(r'```(?:python)?\s*\n(.*?)```', re.DOTALL)

def _extract_code(text):
    m = _CODE_RE.search(text)
    if m:
        return m.group(1).strip()
    # Bare code: has indented lines + programming keywords
    lines = text.strip().splitlines()
    if len(lines) > 2 and any(kw in text for kw in ('def ', 'for ', 'while ', 'print(', 'import ', '    ')):
        return text.strip()
    return None

def clean_for_speech(text):
    """Remove URLs, command tokens, code blocks and markdown before Tony speaks."""
    text = _CODE_RE.sub('I have written the code.', text)
    text = re.sub(r'(SEARCH|OPEN_TAB|OPEN_APP|CLOSE_APP|RUN_CODE|OPEN_VSCODE)\[[^\]]*\]', '', text)
    text = re.sub(r'https?://\S+', 'that page', text)
    text = re.sub(r'\*+([^*]+)\*+', r'\1', text)
    return text.strip()

ECHO_WINDOW = 4.0
ECHO_OVERLAP = 0.4
CONTINUE_KEYWORDS  = {"yes", "yeah", "sure", "continue", "please", "go on", "go ahead", "yep", "of course"}
SHUTDOWN_TRIGGERS  = {"shut down", "shutdown", "turn off", "go to sleep", "goodbye tony",
                      "bye tony", "stop tony", "exit tony", "sleep tony"}
CONFIRM_WORDS      = {"yes", "yeah", "sure", "confirm", "do it", "yep", "go ahead"}
# Actions whose response is just "Done" — never skipped even when queue is full
SIMPLE_ACTION_WORDS = {"open", "close", "launch", "tab", "scroll", "press", "start", "stop",
                       "next", "previous", "prev", "reopen", "new", "minimize", "maximize"}

# Order guardrails
_MAX_SINGLE_ITEM  = 6   # max quantity of one item per order command
_MAX_DAILY_ITEMS  = 10  # max total items ordered per day (persisted to disk)

_ORDER_COUNT_FILE = Path.home() / ".tony" / "order_count.json"
_ORDER_COUNT_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load_order_count() -> int:
    try:
        data = json.loads(_ORDER_COUNT_FILE.read_text())
        if data.get("date") == str(date.today()):
            return int(data.get("total", 0))
    except Exception:
        pass
    return 0

def _save_order_count(total: int):
    _ORDER_COUNT_FILE.write_text(json.dumps({"date": str(date.today()), "total": total}))

def _reset_order_count():
    _save_order_count(0)

def _word_overlap(text1, text2):
    w1 = set(text1.lower().split())
    w2 = set(text2.lower().split())
    if not w1:
        return 0.0
    return len(w1 & w2) / len(w1)

def is_echo(user_text):
    if len(user_text.split()) < 3:
        return False
    if time.time() - get_last_speech_end_time() > ECHO_WINDOW:
        return False
    last = get_last_spoken_text()
    if not last:
        return False
    w_user = set(user_text.lower().split())
    w_last = set(last.lower().split())
    # Strongest signal: every word the mic caught exists in Tony's last sentence
    if w_user.issubset(w_last):
        return True
    return len(w_user & w_last) / len(w_user) > ECHO_OVERLAP

def wants_to_continue(text):
    return any(kw in text.lower() for kw in CONTINUE_KEYWORDS)

def is_shutdown_trigger(text):
    t = text.lower()
    return any(trigger in t for trigger in SHUTDOWN_TRIGGERS)

def is_simple_action(text):
    """True when the query is likely an open/close/tab/scroll command — always process these."""
    return bool(set(text.lower().split()) & SIMPLE_ACTION_WORDS)

def process_response(user_text):
    # Inject Blinkit context so the brain knows the browser is open
    brain_input = user_text
    if blinkit_is_open():
        brain_input = f"[Blinkit is currently open] {user_text}"
    agent_text = get_response(brain_input)
    _p("### [Brain]: ", agent_text, "brain")

    # Save any code block the brain wrote
    code = _extract_code(agent_text)
    if code:
        save_code(code)

    if "RUN_CODE" in agent_text:
        _p("### [Thinking]: ", "Running code...", "think")
        output = run_code()
        agent_text = f"Output: {output}"

    elif "OPEN_VSCODE" in agent_text:
        open_in_vscode()
        agent_text = "Opened in VS Code."

    elif "SEARCH[" in agent_text or re.match(r'SEARCH\s+\S', agent_text):
        # Support both SEARCH[query] and bare SEARCH query (model sometimes drops brackets)
        if "SEARCH[" in agent_text:
            query = agent_text.split("SEARCH[")[1].split("]")[0]
        else:
            query = re.sub(r'^SEARCH\s+', '', agent_text, flags=re.IGNORECASE).strip()
        if not is_instant_query(query):
            speak("Searching.")
        _p("### [Thinking]: ", f"Searching for {query}", "think")
        data = search_web(query)
        # Weather API returns a clean one-liner (no "- title:" prefix) — skip LLM summarize
        if data and not data.startswith("- ") and "°" in data:
            _p("### [Thinking]: ", "Weather API — skipping summarize.", "think")
            agent_text = data
            store_response(data)   # put actual weather into history so follow-ups don't re-search
        else:
            _p("### [Thinking]: ", "Summarizing.", "think")
            agent_text = summarize_search(query, data)

    elif "GOOGLE_SEARCH[" in agent_text:
        q = agent_text.split("GOOGLE_SEARCH[")[1].split("]")[0]
        threading.Thread(target=open_url, args=(f"https://www.google.com/search?q={q.replace(' ', '+')}",), daemon=True).start()
        agent_text = f"Opened Google search for {q}."

    elif "OPEN_TAB[" in agent_text or re.match(r'OPEN_TAB\s+\S', agent_text):
        if "OPEN_TAB[" in agent_text:
            url = agent_text.split("OPEN_TAB[")[1].split("]")[0]
        else:
            url = re.sub(r'^OPEN_TAB\s+', '', agent_text, flags=re.IGNORECASE).strip()
        threading.Thread(target=open_url, args=(url,), daemon=True).start()
        agent_text = "Done, opened it."

    elif "OPEN_APP[" in agent_text or re.match(r'OPEN_APP\s+\S', agent_text):
        if "OPEN_APP[" in agent_text:
            app = agent_text.split("OPEN_APP[")[1].split("]")[0]
        else:
            app = re.sub(r'^OPEN_APP\s+', '', agent_text, flags=re.IGNORECASE).strip()
        threading.Thread(target=open_app, args=(app,), daemon=True).start()
        agent_text = "Done."

    elif "CLOSE_TAB" in agent_text:
        threading.Thread(target=close_tab, daemon=True).start()
        agent_text = "Done, tab closed."

    elif "NEW_TAB" in agent_text:
        threading.Thread(target=new_tab, daemon=True).start()
        agent_text = "Done."

    elif "NEXT_TAB" in agent_text:
        threading.Thread(target=next_tab, daemon=True).start()
        agent_text = "Done."

    elif "PREV_TAB" in agent_text:
        threading.Thread(target=prev_tab, daemon=True).start()
        agent_text = "Done."

    elif "REOPEN_TAB" in agent_text:
        threading.Thread(target=reopen_tab, daemon=True).start()
        agent_text = "Done, reopened it."

    elif "SCROLL_DOWN" in agent_text:
        threading.Thread(target=scroll_down, daemon=True).start()
        agent_text = "Done."

    elif "SCROLL_UP" in agent_text:
        threading.Thread(target=scroll_up, daemon=True).start()
        agent_text = "Done."

    elif "PRESS_KEY[" in agent_text:
        key = agent_text.split("PRESS_KEY[")[1].split("]")[0]
        threading.Thread(target=press_key, args=(key,), daemon=True).start()
        agent_text = "Done."

    elif "CLOSE_APP[" in agent_text or re.match(r'CLOSE_APP\s+\S', agent_text):
        if "CLOSE_APP[" in agent_text:
            app = agent_text.split("CLOSE_APP[")[1].split("]")[0]
        else:
            app = re.sub(r'^CLOSE_APP\s+', '', agent_text, flags=re.IGNORECASE).strip()
        threading.Thread(target=close_app, args=(app,), daemon=True).start()
        agent_text = "Done."

    elif "MINIMIZE_APP[" in agent_text:
        app = agent_text.split("MINIMIZE_APP[")[1].split("]")[0]
        threading.Thread(target=minimize_app, args=(app,), daemon=True).start()
        agent_text = "Done, minimized."

    elif "BLINKIT_LOGIN" in agent_text:
        speak("Opening Blinkit for login.")
        def _do_login():
            result = blinkit_login()
            speak(result)
        threading.Thread(target=_do_login, daemon=True).start()
        return "Opening Blinkit for login."

    elif "BLINKIT_ORDER[" in agent_text:
        raw = agent_text.split("BLINKIT_ORDER[")[1].split("]")[0]
        item, qty = parse_blinkit_order(raw)
        if qty > _MAX_SINGLE_ITEM:
            return f"I can add at most {_MAX_SINGLE_ITEM} of the same item. Shall I add {_MAX_SINGLE_ITEM}?"
        today_total = _load_order_count()
        if today_total + qty > _MAX_DAILY_ITEMS:
            remaining = max(_MAX_DAILY_ITEMS - today_total, 0)
            return f"You've ordered {today_total} items today. Daily limit is {_MAX_DAILY_ITEMS}. I can add {remaining} more."
        _save_order_count(today_total + qty)
        speak(f"Adding {item} to your Blinkit cart.")
        def _do_order(i=item, q=qty):
            result = blinkit_add_to_cart(i, q)
            speak(result)
        threading.Thread(target=_do_order, daemon=True).start()
        return f"Adding {item} to your Blinkit cart."

    elif "BLINKIT_REMOVE[" in agent_text:
        raw = agent_text.split("BLINKIT_REMOVE[")[1].split("]")[0]
        item, qty = parse_blinkit_remove(raw)
        label = f"{qty}x " if qty else "all "
        speak(f"Removing {label}{item} from your Blinkit cart.")
        def _do_remove(i=item, q=qty):
            result = blinkit_remove_from_cart(i, q)
            speak(result)
        threading.Thread(target=_do_remove, daemon=True).start()
        return f"Removing {label}{item} from Blinkit cart."

    elif "BLINKIT_PAY_NOW" in agent_text:
        return "__BLINKIT_PAY_PENDING__"

    elif "BLINKIT_CHECKOUT" in agent_text:
        speak("Opening Blinkit checkout.")
        def _do_checkout():
            result = blinkit_open_checkout()
            speak(result)
        threading.Thread(target=_do_checkout, daemon=True).start()
        return "Opening Blinkit checkout."

    elif "BLINKIT_CART" in agent_text:
        speak("Checking your Blinkit cart.")
        def _do_cart():
            result = blinkit_check_cart()
            speak(result)
        threading.Thread(target=_do_cart, daemon=True).start()
        return "Checking your Blinkit cart."

    elif "ZOMATO_LOGIN" in agent_text:
        speak("Opening Zomato for login.")
        def _do_z_login():
            result = zomato_login()
            speak(result)
        threading.Thread(target=_do_z_login, daemon=True).start()
        return "Opening Zomato for login."

    elif "ZOMATO_ORDER[" in agent_text:
        raw = agent_text.split("ZOMATO_ORDER[")[1].split("]")[0]
        dish, restaurant = parse_zomato_order(raw)
        today_total = _load_order_count()
        if today_total + 1 > _MAX_DAILY_ITEMS:
            remaining = max(_MAX_DAILY_ITEMS - today_total, 0)
            return f"You've ordered {today_total} items today. Daily limit is {_MAX_DAILY_ITEMS}. I can add {remaining} more."
        _save_order_count(today_total + 1)
        label = f"{dish} from {restaurant}" if restaurant else dish
        speak(f"Ordering {label} on Zomato.")
        def _do_z_order(d=dish, r=restaurant):
            result = zomato_order(d, r)
            speak(result)
        threading.Thread(target=_do_z_order, daemon=True).start()
        return f"Ordering {label} on Zomato."

    elif "ZOMATO_CART" in agent_text:
        speak("Checking your Zomato cart.")
        def _do_z_cart():
            result = zomato_check_cart()
            speak(result)
        threading.Thread(target=_do_z_cart, daemon=True).start()
        return "Checking your Zomato cart."

    elif "RESET_ORDER_COUNT" in agent_text:
        _reset_order_count()
        return "Order count reset. You have 10 items available today."

    return agent_text

def main():
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 0.5   # was 0.8 — saves 300 ms per turn
    recognizer.phrase_threshold = 0.3

    audio_queue = queue.Queue()

    # Snapshot is_speaking at callback time — if Tony was still talking when
    # the user's phrase completed, it's an interruption.
    def audio_callback(rec, audio):
        audio_queue.put((audio, is_speaking))

    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.5)
    # Set threshold to 2× calibrated ambient + a hard floor of 600.
    # This filters out background TV / distant voices (typically 1–2× ambient)
    # while still catching direct speech (typically 5–10× ambient).
    recognizer.energy_threshold = max(recognizer.energy_threshold * 2, 600)
    print(f"Tony is online. (energy threshold: {recognizer.energy_threshold:.0f})")

    stop_bg = recognizer.listen_in_background(mic, audio_callback, phrase_time_limit=10)
    pending_old_response  = None
    shutdown_pending      = False
    blinkit_pay_pending   = False  # waiting for user to confirm order
    queue_depth           = 0   # questions processed while Tony was speaking
    tony_was_speaking     = False

    try:
        while True:
            try:
                audio, was_tony_speaking = audio_queue.get(timeout=1)
            except queue.Empty:
                # Reset queue depth counter when Tony finishes speaking
                if tony_was_speaking and not is_speaking:
                    queue_depth = 0
                tony_was_speaking = is_speaking
                continue

            tony_was_speaking = is_speaking

            try:
                user_text = transcribe_audio(audio)
            except Exception as e:
                print(f"Transcription error: {e}")
                continue

            if not user_text or len(user_text.split()) < 2:
                continue

            if is_echo(user_text):
                _p("[Echo filtered]: ", user_text, "dim")
                continue

            # ── Blinkit order confirmation ─────────────────────────────────
            if blinkit_pay_pending:
                _p("\n[You]: ", user_text, "you")
                if any(w in user_text.lower() for w in CONFIRM_WORDS):
                    blinkit_pay_pending = False
                    speak("Placing the order now.")
                    def _do_pay():
                        result = blinkit_pay_now()
                        speak(result)
                    threading.Thread(target=_do_pay, daemon=True).start()
                else:
                    blinkit_pay_pending = False
                    _p("[Tony]: ", "Order cancelled.", "tony")
                    speak("Order cancelled.")
                continue

            # ── Shutdown flow ──────────────────────────────────────────────
            if shutdown_pending:
                _p("\n[You]: ", user_text, "you")
                if any(w in user_text.lower() for w in CONFIRM_WORDS):
                    speak("Goodbye.")
                    time.sleep(2.5)
                    stop_bg(wait_for_stop=False)
                    sys.exit(0)
                else:
                    shutdown_pending = False
                    _p("[Tony]: ", "Shutdown cancelled.", "tony")
                    speak("Shutdown cancelled.")
                continue

            if is_shutdown_trigger(user_text):
                shutdown_pending = True
                _p("\n[You]: ", user_text, "you")
                _p("[Tony]: ", "Shall I shut down? Say yes to confirm.", "tony")
                speak("Shall I shut down? Say yes to confirm.")
                continue

            # ── Queue depth guard — skip complex questions when 2+ pending ─
            if is_speaking and not is_simple_action(user_text):
                if queue_depth >= 2:
                    _p("[Skipped — queue full]: ", user_text, "dim")
                    continue
                queue_depth += 1

            def _handle_response(resp):
                nonlocal blinkit_pay_pending
                if resp == "__BLINKIT_PAY_PENDING__":
                    blinkit_pay_pending = True
                    msg = "Ready to place the order. Say yes to confirm, or no to cancel."
                    _p("[Tony]: ", msg, "tony")
                    speak(msg)
                else:
                    _p("[Tony]: ", clean_for_speech(resp), "tony")
                    speak(clean_for_speech(resp))

            if was_tony_speaking:
                interrupted_text = get_last_spoken_text()
                stop_speaking()
                _p("\n[Interrupted]: ", user_text, "dim")

                agent_text = process_response(user_text)
                if interrupted_text:
                    pending_old_response = interrupted_text
                    if agent_text == "__BLINKIT_PAY_PENDING__":
                        _handle_response(agent_text)
                    else:
                        _p("[Tony]: ", clean_for_speech(agent_text), "tony")
                        speak(clean_for_speech(agent_text) + " Also, shall I continue with what I was saying?")
                else:
                    _handle_response(agent_text)

            elif pending_old_response is not None:
                _p("\n[You]: ", user_text, "you")
                if wants_to_continue(user_text):
                    response = "Continuing from where I left off. " + pending_old_response
                    _p("[Tony]: ", clean_for_speech(response), "tony")
                    speak(clean_for_speech(response))
                    pending_old_response = None
                else:
                    pending_old_response = None
                    _handle_response(process_response(user_text))

            else:
                _p("\n[You]: ", user_text, "you")
                _handle_response(process_response(user_text))

    finally:
        stop_bg(wait_for_stop=False)

if __name__ == "__main__":
    main()

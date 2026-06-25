# brain.py
import time
from datetime import date
from sarvamai import SarvamAI
from groq import Groq
from config import SARVAM_KEY, GROQ_KEY, LOCATION, LLM_PROVIDER

# Lazy init — keys are loaded from .env by config.py before this runs
_sarvam = SarvamAI(api_subscription_key=SARVAM_KEY, timeout=60.0)
_groq   = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

GROQ_MODEL   = "llama-3.1-8b-instant"
SARVAM_MODEL = "sarvam-30b"

_history = []

def _screen_size():
    try:
        import pyautogui
        w, h = pyautogui.size()
        return f"{w}x{h}"
    except Exception:
        return "1920x1080"

def _system_prompt():
    today = date.today().strftime("%B %d, %Y")
    screen = _screen_size()
    return {
        "role": "system",
        "content": (
            f"You are Tony, a witty voice assistant in {LOCATION}. Date: {today}. Screen resolution: {screen}. "
            "Reply in one short sentence or one action token — nothing else. Be decisive, no deliberation. "
            "Dry wit allowed; serious on spiritual/political topics. "
            "Never invent facts. Temperatures always in Celsius. "
            "If corrected, immediately re-search. "
            "For current time or date, use SEARCH[current time] — the system will return the local PC clock, no internet needed. "
            "When asked about weather and you don't already have current data in context, search for '[city] weather forecast'. "
            "If weather data is already in the conversation, reason from it directly — do not search again. "
            "Include temperature, conditions, and umbrella advice when relevant. "
            "When the user says 'recent', 'past', 'yesterday', 'last week' etc., keep that word in the SEARCH query — do not replace it with a specific date. "
            "NEVER delete files, modify the filesystem, run shell commands, or trigger system shutdown/restart/hibernate. "
            "Output exactly one action token OR one plain sentence — nothing else. "
            "When the user's message starts with [Blinkit is currently open], treat any grocery/food item request as BLINKIT_ORDER[item] — do NOT use SEARCH for it. "
            "Action tokens (square brackets are REQUIRED): "
            "SEARCH[query] | GOOGLE_SEARCH[query] | OPEN_TAB[url] | OPEN_APP[name] | CLOSE_APP[name] | MINIMIZE_APP[name] | CLOSE_TAB | RUN_CODE | OPEN_VSCODE. "
            "Use MINIMIZE_APP[name] to minimize a window (e.g. MINIMIZE_APP[firefox]). "
            "Mouse control: MOUSE_MOVE[x,y] | MOUSE_CLICK[x,y] | MOUSE_CLICK | MOUSE_RIGHT_CLICK[x,y] | MOUSE_DRAG[x1,y1,x2,y2]. "
            "Use mouse tokens when the user wants to move the cursor, click somewhere, or draw (e.g. in MS Paint). "
            "Coordinates are absolute screen pixels. Screen resolution is provided above — use it to calculate positions. "
            "Example: MOUSE_DRAG[100,200,400,200] draws a horizontal line in Paint. "
            "Use GOOGLE_SEARCH[query] when the user explicitly says 'search on Google' or 'Google it'. "
            "Example: SEARCH[Bengaluru weather today]  — never write SEARCH Bengaluru weather today. "
            "To write code: reply with just the code block. To run it: RUN_CODE. To open in editor: OPEN_VSCODE. "
            "Tab control: CLOSE_TAB | CLOSE_TAB[name] | NEW_TAB | NEXT_TAB | PREV_TAB | REOPEN_TAB | SCROLL_DOWN | SCROLL_UP | PRESS_KEY[key]. "
            "CLOSE_TAB closes the current tab. CLOSE_TAB[youtube] closes a specific tab by name — Tony will scan through open tabs to find it. CLOSE_APP[name] quits the whole app. "
            "Use SCROLL_DOWN / SCROLL_UP to scroll the page. Use PRESS_KEY[enter] to press Enter, PRESS_KEY[tab] to tab, etc. "
            "Blinkit grocery ordering: BLINKIT_LOGIN | BLINKIT_ORDER[item] | BLINKIT_ORDER[2 milk] | BLINKIT_REMOVE[item] | BLINKIT_REMOVE[2 milk] | BLINKIT_CART | BLINKIT_CHECKOUT. "
            "Use BLINKIT_CHECKOUT when user says 'checkout', 'open cart', or 'go to checkout'. "
            "Use BLINKIT_PAY_NOW when user says 'pay now', 'confirm order', 'place order', or 'proceed to pay' — this clicks the Pay Now button. "
            "Use BLINKIT_ORDER[item] when the user wants to add something from Blinkit. "
            "Use BLINKIT_REMOVE[item] when the user wants to remove an item from their Blinkit cart. "
            "Use BLINKIT_REMOVE[2 milk] to remove a specific quantity; no number = remove all. "
            "Prefix quantity before item: BLINKIT_ORDER[2 milk], BLINKIT_ORDER[1 bread]. "
            "NEVER order more than 6 of any single item. If asked for more, refuse and explain the limit. "
            "Use BLINKIT_LOGIN when user says 'log in to Blinkit' or 'Blinkit login'. "
            "Use BLINKIT_CART when user asks what's in their Blinkit cart. "
            "Zomato food ordering: ZOMATO_LOGIN | ZOMATO_ORDER[dish] | ZOMATO_ORDER[dish from restaurant] | ZOMATO_CART. "
            "Use ZOMATO_ORDER[dish] when the user wants to order food from Zomato. "
            "If user names a restaurant: ZOMATO_ORDER[butter chicken from Punjabi Dhaba]. "
            "NEVER order more than 6 of any single item on Zomato either. "
            "Use ZOMATO_LOGIN when user says 'log in to Zomato' or 'Zomato login'. "
            "Use ZOMATO_CART when user asks what's in their Zomato cart. "
            "Use RESET_ORDER_COUNT if the user says 'reset order count' or 'clear order limit'."
        )
    }

def _build_messages(extra=None):
    msgs = [_system_prompt()] + _history
    if extra:
        msgs.append(extra)
    return msgs

def _call_api(messages):
    delays = [0, 0.5, 1.5]
    for attempt, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        try:
            if LLM_PROVIDER == "groq" and _groq:
                response = _groq.chat.completions.create(
                    model=GROQ_MODEL, messages=messages, max_tokens=1024, temperature=0.7
                )
            else:
                response = _sarvam.chat.completions(
                    model=SARVAM_MODEL, messages=messages, max_tokens=4096
                )
            if response and response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            tokens = getattr(getattr(response, "usage", None), "completion_tokens", "?")
            reason = response.choices[0].finish_reason if response and response.choices else "?"
            print(f"Brain: no content (attempt {attempt + 1}) — {tokens} tokens, finish={reason}")
        except Exception as e:
            print(f"Brain Error (attempt {attempt + 1}): {type(e).__name__}: {e}")
    return None

def store_response(text):
    """Add a final assistant reply to history (used when we bypass summarize)."""
    global _history
    _history.append({"role": "assistant", "content": text})
    if len(_history) > 12:
        _history = _history[-12:]

def get_response(user_text):
    global _history
    _history.append({"role": "user", "content": user_text})
    if len(_history) > 12:
        _history = _history[-12:]

    result = _call_api(_build_messages())
    if result:
        _history.append({"role": "assistant", "content": result})
        return result

    _history.pop()   # don't keep failed turns
    return "Sorry, I couldn't get that. Could you rephrase?"

def summarize_search(query, data):
    """Summarise search results without storing raw data in history."""
    global _history

    def _try(prompt):
        extra = {"role": "user", "content": prompt}
        return _call_api(_build_messages(extra=extra))

    # Full attempt
    result = _try(
        f"Search results for '{query}':\n{data}\n"
        "One sentence summary relevant to the query. Include exact numbers/names. "
        "If no relevant data, say so."
    )

    # Simpler fallback if full attempt fails
    if not result:
        time.sleep(1.0)
        result = _try(f"Summarise in one sentence: {data[:300]}")

    if result:
        _history.append({"role": "assistant", "content": result})
        if len(_history) > 12:
            _history = _history[-12:]
        return result

    # Last resort: surface the raw first line so the user gets something
    first = data.split('\n')[0][:200] if data and data != "Search failed." else None
    if first:
        print(f"[Fallback raw result]: {first}")
        return f"I had trouble summarising, but the top result says: {first}"
    return "My search returned nothing useful for that query."

# brain.py
import time
from datetime import date
from sarvamai import SarvamAI
from groq import Groq
from config import SARVAM_KEY, GROQ_KEY, LOCATION, LLM_PROVIDER

_sarvam = SarvamAI(api_subscription_key=SARVAM_KEY, timeout=60.0)
_groq   = Groq(api_key=GROQ_KEY)

GROQ_MODEL   = "llama-3.3-70b-versatile"
SARVAM_MODEL = "sarvam-30b"

_history = []

def _system_prompt():
    today = date.today().strftime("%B %d, %Y")
    return {
        "role": "system",
        "content": (
            f"You are Tony, a witty voice assistant in {LOCATION}. Date: {today}. "
            "Reply in one short sentence or one action token — nothing else. Be decisive, no deliberation. "
            "Dry wit allowed; serious on spiritual/political topics. "
            "Never invent facts. Temperatures always in Celsius. "
            "If corrected, immediately re-search. "
            "NEVER delete files, modify the filesystem, or run shell commands. "
            "Actions (pick one, no other text): "
            "SEARCH[query] | OPEN_TAB[url] | OPEN_APP[name] | CLOSE_APP[name] | plain sentence"
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
            if LLM_PROVIDER == "groq":
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

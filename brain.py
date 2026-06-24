# brain.py
import time
from datetime import date
from sarvamai import SarvamAI
from config import SARVAM_KEY, LOCATION

client = SarvamAI(api_subscription_key=SARVAM_KEY, timeout=60.0)

_history = []

def _system_prompt():
    today = date.today().strftime("%B %d, %Y")
    return {
        "role": "system",
        "content": (
            f"You are Tony, a voice assistant. Location: {LOCATION}. Today's date: {today}. "

            "PERSONALITY: Dry wit, one quip per topic at most. "
            "Never repeat a joke or metaphor. Skip humour when user is frustrated. "
            "Serious and respectful on spiritual, religious, or political topics. "

            "ACCURACY: NEVER confabulate. Only state facts from search results or the current conversation. "
            "Preface search-derived data with 'according to what I found' so the user knows it may not be 100% reliable. "
            "When reporting numbers (temperatures, prices, scores), reproduce the exact value and unit from the source — never convert. "
            "When the user corrects you, accept it gracefully and offer to re-search to verify — never defend a previous answer stubbornly. "
            "If search results contain conflicting data, mention the discrepancy rather than picking one arbitrarily. "

            "CONTEXT: Voice interface. STT garbles words — infer intent from context "
            "(e.g. 'life score' / 'knife score' after a sports question = 'live score'). "

            "ACTIONS — output exactly one, no extra text: "
            "1. Plain sentence (default, keep it short). "
            "2. SEARCH[specific query with year] — to fetch data you will speak aloud. "
            "3. OPEN_TAB[https://...] — only when user says 'open', 'show me', or 'go to'. "
            "4. OPEN_APP[app name] — launch a desktop app. "
            "5. CLOSE_APP[app name] — close a desktop app."
        )
    }

def _build_messages(extra=None):
    msgs = [_system_prompt()] + _history
    if extra:
        msgs.append(extra)
    return msgs

def _call_api(messages):
    for attempt in range(2):
        try:
            response = client.chat.completions(model="sarvam-30b", messages=messages)
            if response and response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Brain Error (attempt {attempt + 1}): {e}")
        if attempt == 0:
            time.sleep(0.8)
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
    extra = {
        "role": "user",
        "content": (
            f"Search results for '{query}':\n{data}\n"
            "Summarise in one sentence, focusing only on results directly relevant to the query. "
            "Include exact scores, names, or numbers as they appear in the source. "
            "If results conflict (e.g. different scores), mention both. "
            "If no relevant data is found, say so honestly."
        )
    }
    result = _call_api(_build_messages(extra=extra))
    if result:
        # Only the compact summary enters history, not the raw data
        _history.append({"role": "assistant", "content": result})
        if len(_history) > 12:
            _history = _history[-12:]
        return result
    return "I found results but couldn't summarise them."

# brain.py
import time
from datetime import date
from sarvamai import SarvamAI
from config import SARVAM_KEY, LOCATION

client = SarvamAI(api_subscription_key=SARVAM_KEY, timeout=60.0)

_history = []   # excludes system prompt; trimmed to last 10 exchanges

def _system_prompt():
    today = date.today().strftime("%B %d, %Y")
    return {
        "role": "system",
        "content": (
            f"You are Tony, a voice assistant. Location: {LOCATION}. Today's date: {today}. "
            "RULES: "
            "1. Respond in one precise sentence unless the user asks for detail. "
            "2. For live or current data (weather, scores, news, prices) always output SEARCH[query] "
            "   — include the current year and be specific (e.g. SEARCH[2026 FIFA World Cup live scores today]). "
            "3. To open a website output OPEN_TAB[https://...] — always a full URL. "
            "4. To launch a desktop app output OPEN_APP[app name]. "
            "5. To close a desktop app output CLOSE_APP[app name]."
        )
    }

def _build_messages():
    return [_system_prompt()] + _history

def get_response(user_text):
    global _history
    _history.append({"role": "user", "content": user_text})
    if len(_history) > 20:
        _history = _history[-20:]

    for attempt in range(2):
        try:
            response = client.chat.completions(model="sarvam-30b", messages=_build_messages())
            if response and response.choices and response.choices[0].message.content:
                agent_text = response.choices[0].message.content.strip()
                _history.append({"role": "assistant", "content": agent_text})
                return agent_text
        except Exception as e:
            print(f"Brain Error (attempt {attempt + 1}): {e}")
        if attempt == 0:
            time.sleep(0.8)

    # All attempts failed — remove the user message so bad context doesn't accumulate
    _history.pop()
    return "Sorry, I couldn't get that. Could you rephrase?"

def update_history_with_search(query, data):
    _history.append({"role": "user", "content": f"Results for '{query}': {data}. Summarize in one sentence."})

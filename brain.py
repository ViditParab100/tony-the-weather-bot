# brain.py
from sarvamai import SarvamAI
from config import SARVAM_KEY, LOCATION

client = SarvamAI(api_subscription_key=SARVAM_KEY, timeout=60.0)

# The System Prompt now acts as your "One-Liner Guard"
chat_history = [
    {
        "role": "system", 
        "content": (
            f"You are Tony. Location: {LOCATION}. "
            "RULES: 1. Respond in one precise sentence unless the user asks for 'detail' or 'explanation'. "
            "2. If you need live data, output SEARCH[query]. "
            "3. If you need to open a site, output OPEN_TAB[url]."
        )
    }
]

def get_response(user_text):
    chat_history.append({"role": "user", "content": user_text})
    
    try:
        response = client.chat.completions(model="sarvam-30b", messages=chat_history)
        
        if response and response.choices and response.choices[0].message.content:
            agent_text = response.choices[0].message.content.strip()
        else:
            agent_text = "I'm having trouble thinking."
        
        chat_history.append({"role": "assistant", "content": agent_text})
        return agent_text
        
    except Exception as e:
        print(f"Brain Error: {e}")
        return "I'm having a connection issue."

def update_history_with_search(query, data):
    # Added "Answer briefly" to ensure the search summary also stays short
    chat_history.append({"role": "user", "content": f"Results for '{query}': {data}. Summarize in one sentence."})
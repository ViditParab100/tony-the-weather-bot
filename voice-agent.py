import os
import random
import speech_recognition as sr
from faster_whisper import WhisperModel
import tempfile
from sarvamai import SarvamAI
from duckduckgo_search import DDGS

# --- 1. SETUP LLM BRAIN ---
SARVAM_KEY = os.environ.get("SARVAM_API_KEY") 
client = SarvamAI(api_subscription_key=SARVAM_KEY, timeout=60.0)

# The 6 filler phrases for exhaustive searches
FILLERS = [
    "Let me pull that up for you.",
    "Checking the live web now.",
    "Give me just a second to find that.",
    "I'm on it. Searching the database.",
    "Let me verify the latest data on that.",
    "Accessing the web, stand by."
]

# Tony's Master Instructions
chat_history = [
    {
        "role": "system", 
        "content": (
            "Your name is Tony. You are a highly advanced, concise AI assistant. "
            "If you can answer a question directly based on general knowledge, do so briefly. "
            "HOWEVER, if the user asks for real-time information (like weather, news, sports scores) "
            "or specific facts you are unsure about, you MUST output EXACTLY this format: SEARCH[your query here] "
            "Do not output anything else if you need to search."
        )
    }
]

def search_web(query):
    """Fetches the top 3 results from DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            # Clean up the results into a readable string for the LLM
            search_data = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
            return search_data if search_data else "No results found."
    except Exception as e:
        return f"Search failed: {e}"

def main():
    # --- 2. SETUP EARS ---
    print("Loading Whisper model...")
    model = WhisperModel("./whisper-base", device="cpu", compute_type="int8") 
    print("Tony is online and listening! (Press Ctrl+C to stop)\n")

    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.5)

        while True:
            try:
                # 3. Listen
                print("Listening...")
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=15)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
                    temp_wav.write(audio.get_wav_data())
                    temp_file_path = temp_wav.name

                # 4. Transcribe
                segments, info = model.transcribe(temp_file_path, beam_size=5)
                user_text = "".join([segment.text for segment in segments]).strip()
                os.remove(temp_file_path)

                if not user_text:
                    continue

                print(f"\n[You]: {user_text}")
                chat_history.append({"role": "user", "content": user_text})
                
                # --- 5. THE BRAIN (Phase 1: Decide) ---
                response = client.chat.completions(
                    model="sarvam-30b",
                    messages=chat_history
                )
                agent_text = response.choices[0].message.content.strip()

                # --- 6. THE INTERCEPTOR (Web Search Logic) ---
                if "SEARCH[" in agent_text:
                    # Extract the query from between the brackets
                    query = agent_text.split("SEARCH[")[1].split("]")[0]
                    
                    # Instantly output the filler
                    filler = random.choice(FILLERS)
                    print(f"[Tony]: {filler}  <-- (This is where the voice will speak instantly while searching)")
                    
                    # Perform the actual web search
                    print(f"       [System: Searching web for '{query}'...]")
                    web_data = search_web(query)
                    
                    # FIX 1: We must save his SEARCH attempt to the memory so the conversation flows logically
                    chat_history.append({"role": "assistant", "content": agent_text})
                    
                    # FIX 2: Feed the live data back as a "user" message, NOT a "system" message
                    data_injection = (
                        f"Web results for '{query}':\n{web_data}\n\n"
                        "Based on this data, answer my original question briefly. DO NOT use the SEARCH tag again."
                    )
                    chat_history.append({"role": "user", "content": data_injection})
                    
                    # Get the final, data-backed answer from Tony
                    final_response = client.chat.completions(
                        model="sarvam-30b",
                        messages=chat_history
                    )
                    agent_text = final_response.choices[0].message.content.strip()

                # --- 7. FINAL OUTPUT ---
                print(f"[Tony]: {agent_text}\n")
                print("-" * 50)
                
                # Save only the final answer to memory so Tony remembers the context
                chat_history.append({"role": "assistant", "content": agent_text})

            except KeyboardInterrupt:
                print("\nShutting Tony down.")
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
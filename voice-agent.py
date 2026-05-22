import os
import random
import threading
import webbrowser
import speech_recognition as sr
import geocoder
import tempfile
import io
import soundfile as sf
import sounddevice as sd
from faster_whisper import WhisperModel
from sarvamai import SarvamAI
from ddgs import DDGS

# --- 1. SETUP ---
SARVAM_KEY = os.environ.get("SARVAM_API_KEY") 
client = SarvamAI(api_subscription_key=SARVAM_KEY, timeout=60.0)

# Threading lock to prevent TTS crashes
tts_lock = threading.Lock()

def speak_async(text):
    """Speaks natural speech via Sarvam TTS."""
    def _speak():
        # Only one voice at a time!
        with tts_lock:
            try:
                response = client.text_to_speech.convert(
                    text=text, model="bulbul:v3", speaker="shubh", target_language_code="en-IN" 
                )
                audio_data = response.audios[0]
                import base64
                audio_bytes = base64.b64decode(audio_data)
                
                data, samplerate = sf.read(io.BytesIO(audio_bytes))
                sd.play(data, samplerate)
                sd.wait()
            except Exception as e:
                print(f"TTS Error: {e}")
            
    threading.Thread(target=_speak).start()

def get_location():
    try: return geocoder.ip('me').city
    except: return "Bengaluru"

# --- 2. BRAIN & SEARCH ---
chat_history = [
    {"role": "system", "content": f"You are Tony. Location: {get_location()}. Be concise. If you need data, output SEARCH[query]. If you need to open a site, output OPEN_TAB[url]. Answer in < 2 sentences."}
]

def search_web(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=2))
            return "\n".join([f"- {r['title']}" for r in results])
    except: return "Search failed."

def main():
    print("Loading models...")
    model = WhisperModel("./whisper-base", device="cpu", compute_type="int8") 
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        print("Tony is online.")

        while True:
            try:
                print("\nListening...")
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=15)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(audio.get_wav_data()); temp_path = f.name
                
                segments, _ = model.transcribe(temp_path, beam_size=2)
                user_text = "".join([s.text for s in segments]).strip()
                os.remove(temp_path)

                if not user_text: continue
                print(f"[You]: {user_text}")
                chat_history.append({"role": "user", "content": user_text})
                
                # --- INTENT ANALYSIS ---
                response = client.chat.completions(model="sarvam-30b", messages=chat_history)
                agent_text = response.choices[0].message.content.strip()

                # --- JARVIS LOGIC ---
                if "SEARCH[" in agent_text:
                    query = agent_text.split("SEARCH[")[1].split("]")[0]
                    
                    # Thinking Out Loud
                    speak_async(f"I am searching for {query}.")
                    print(f"[Tony Thinking]: Searching web for '{query}'...")
                    
                    web_data = search_web(query)
                    
                    # Thinking Out Loud
                    speak_async("Got it. Let me summarize that.")
                    
                    chat_history.append({"role": "assistant", "content": agent_text})
                    chat_history.append({"role": "user", "content": f"Results for '{query}': {web_data}. Answer briefly."})
                    
                    final_response = client.chat.completions(model="sarvam-30b", messages=chat_history)
                    agent_text = final_response.choices[0].message.content.strip()

                elif "OPEN_TAB[" in agent_text:
                    url = agent_text.split("OPEN_TAB[")[1].split("]")[0]
                    speak_async("Opening that now.")
                    webbrowser.open(url)
                    agent_text = "I've opened the page."

                print(f"[Tony]: {agent_text}")
                speak_async(agent_text)
                chat_history.append({"role": "assistant", "content": agent_text})

            except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()
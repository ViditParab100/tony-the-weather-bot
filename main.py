# main.py
import speech_recognition as sr
from ears import transcribe_audio
from mouth import speak, is_speaking  # Import the new flag
from brain import get_response, update_history_with_search
from tools import search_web, open_url
import time

def main():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        print("Tony is online.")

        while True:
            # NEW: Check if Tony is speaking before listening
            if is_speaking:
                time.sleep(0.5)
                continue
                
            print("\nListening...")
            try:
                audio = recognizer.listen(source, timeout=1, phrase_time_limit=10)
                user_text = transcribe_audio(audio)
                if not user_text: continue
                
                print(f"[You]: {user_text}")
                agent_text = get_response(user_text)

                # DEBUG & THINKING OUT LOUD
                if "SEARCH[" in agent_text:
                    query = agent_text.split("SEARCH[")[1].split("]")[0]
                    speak(f"Processing. Searching the web for {query}.")
                    print(f"### [Thinking]: Searching for {query}")
                    
                    data = search_web(query)
                    
                    print(f"### [Thinking]: Summarizing found data.")
                    update_history_with_search(query, data)
                    agent_text = get_response("Summarize this.")
                
                elif "OPEN_TAB[" in agent_text:
                    url = agent_text.split("OPEN_TAB[")[1].split("]")[0]
                    speak("Opening that page for you, sir.")
                    open_url(url)
                    agent_text = "I've opened the page."

                print(f"[Tony]: {agent_text}")
                speak(agent_text)
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    main()
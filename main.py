# main.py
import re
import speech_recognition as sr
import queue
import time
from ears import transcribe_audio
from mouth import speak, is_speaking, stop_speaking, get_last_spoken_text, get_last_speech_end_time
from brain import get_response, update_history_with_search
from tools import search_web, open_url, open_app, close_app

def clean_for_speech(text):
    """Remove URLs, command tokens, and markdown before Tony speaks."""
    text = re.sub(r'(SEARCH|OPEN_TAB|OPEN_APP)\[[^\]]*\]', '', text)
    text = re.sub(r'https?://\S+', 'that page', text)
    text = re.sub(r'\*+([^*]+)\*+', r'\1', text)  # strip **bold** / *italic*
    return text.strip()

ECHO_WINDOW = 4.0   # seconds after TTS ends to apply echo filter
ECHO_OVERLAP = 0.4  # fraction of user words that must match Tony's last words
CONTINUE_KEYWORDS = {"yes", "yeah", "sure", "continue", "please", "go on", "go ahead", "yep", "of course"}

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

def process_response(user_text):
    agent_text = get_response(user_text)

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
        speak("Opening that for you, sir.")
        open_url(url)
        agent_text = "I've opened the page."

    elif "OPEN_APP[" in agent_text:
        app = agent_text.split("OPEN_APP[")[1].split("]")[0]
        speak(f"Opening {app}.")
        open_app(app)
        agent_text = f"I've launched {app}."

    elif "CLOSE_APP[" in agent_text:
        app = agent_text.split("CLOSE_APP[")[1].split("]")[0]
        speak(f"Closing {app}.")
        ok = close_app(app)
        agent_text = f"Done, {app} is closed." if ok else f"I couldn't close {app}."

    return agent_text

def main():
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 0.8
    recognizer.phrase_threshold = 0.3

    audio_queue = queue.Queue()

    # Snapshot is_speaking at callback time — if Tony was still talking when
    # the user's phrase completed, it's an interruption.
    def audio_callback(rec, audio):
        audio_queue.put((audio, is_speaking))

    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.5)
    # Enforce a floor: if calibration lands too low, ambient noise holds
    # the phrase open indefinitely and speech is never detected.
    recognizer.energy_threshold = max(recognizer.energy_threshold, 300)
    print(f"Tony is online. (energy threshold: {recognizer.energy_threshold:.0f})")

    stop_bg = recognizer.listen_in_background(mic, audio_callback, phrase_time_limit=10)
    pending_old_response = None  # What Tony was saying when interrupted

    try:
        while True:
            try:
                audio, was_tony_speaking = audio_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                user_text = transcribe_audio(audio)
            except Exception as e:
                print(f"Transcription error: {e}")
                continue

            if not user_text or len(user_text.split()) < 2:
                continue

            if is_echo(user_text):
                print(f"[Echo filtered]: {user_text}")
                continue

            if was_tony_speaking:
                # User spoke while Tony was talking — interruption
                interrupted_text = get_last_spoken_text()
                stop_speaking()
                print(f"\n[Interrupted]: {user_text}")

                agent_text = process_response(user_text)
                print(f"[Tony]: {agent_text}")

                if interrupted_text:
                    pending_old_response = interrupted_text
                    speak(agent_text + " Also, shall I continue with what I was saying?")
                else:
                    speak(clean_for_speech(agent_text))

            elif pending_old_response is not None:
                # Tony offered to continue — check if user wants to
                print(f"\n[You]: {user_text}")
                if wants_to_continue(user_text):
                    response = "Continuing from where I left off. " + pending_old_response
                    print(f"[Tony]: {response}")
                    speak(clean_for_speech(response))
                    pending_old_response = None
                else:
                    # User moved on — treat as a new question
                    pending_old_response = None
                    agent_text = process_response(user_text)
                    print(f"[Tony]: {agent_text}")
                    speak(clean_for_speech(agent_text))

            else:
                print(f"\n[You]: {user_text}")
                agent_text = process_response(user_text)
                print(f"[Tony]: {agent_text}")
                speak(clean_for_speech(agent_text))

    finally:
        stop_bg(wait_for_stop=False)

if __name__ == "__main__":
    main()

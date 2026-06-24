# main.py
import re
import threading
import speech_recognition as sr
import queue
import time
from colorama import init as colorama_init, Fore, Style
colorama_init()
from ears import transcribe_audio
from mouth import speak, is_speaking, stop_speaking, get_last_spoken_text, get_last_speech_end_time
from brain import get_response, summarize_search
from tools import search_web, open_url, open_app, close_app

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
    _p("### [Brain]: ", agent_text, "brain")

    if "SEARCH[" in agent_text:
        query = agent_text.split("SEARCH[")[1].split("]")[0]
        speak("Searching.")   # non-blocking — runs while search happens
        _p("### [Thinking]: ", f"Searching for {query}", "think")
        data = search_web(query)
        _p("### [Thinking]: ", "Summarizing.", "think")
        agent_text = summarize_search(query, data)

    elif "OPEN_TAB[" in agent_text:
        url = agent_text.split("OPEN_TAB[")[1].split("]")[0]
        threading.Thread(target=open_url, args=(url,), daemon=True).start()
        agent_text = "Done, opened it."

    elif "OPEN_APP[" in agent_text:
        app = agent_text.split("OPEN_APP[")[1].split("]")[0]
        threading.Thread(target=open_app, args=(app,), daemon=True).start()
        agent_text = "Done."

    elif "CLOSE_APP[" in agent_text:
        app = agent_text.split("CLOSE_APP[")[1].split("]")[0]
        threading.Thread(target=close_app, args=(app,), daemon=True).start()
        agent_text = "Done."

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
                _p("[Echo filtered]: ", user_text, "dim")
                continue

            if was_tony_speaking:
                interrupted_text = get_last_spoken_text()
                stop_speaking()
                _p("\n[Interrupted]: ", user_text, "dim")

                agent_text = process_response(user_text)
                _p("[Tony]: ", clean_for_speech(agent_text), "tony")

                if interrupted_text:
                    pending_old_response = interrupted_text
                    speak(clean_for_speech(agent_text) + " Also, shall I continue with what I was saying?")
                else:
                    speak(clean_for_speech(agent_text))

            elif pending_old_response is not None:
                _p("\n[You]: ", user_text, "you")
                if wants_to_continue(user_text):
                    response = "Continuing from where I left off. " + pending_old_response
                    _p("[Tony]: ", clean_for_speech(response), "tony")
                    speak(clean_for_speech(response))
                    pending_old_response = None
                else:
                    pending_old_response = None
                    agent_text = process_response(user_text)
                    _p("[Tony]: ", clean_for_speech(agent_text), "tony")
                    speak(clean_for_speech(agent_text))

            else:
                _p("\n[You]: ", user_text, "you")
                agent_text = process_response(user_text)
                _p("[Tony]: ", clean_for_speech(agent_text), "tony")
                speak(clean_for_speech(agent_text))

    finally:
        stop_bg(wait_for_stop=False)

if __name__ == "__main__":
    main()

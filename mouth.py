import re
import threading
import time
import queue as _q
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro

VOICE = "am_onyx"   # bm_george / bm_lewis / am_fenrir are other options
SPEED = 0.95

_speak_count = 0
is_speaking = False
_stop_requested = False
_last_speech_end_time = 0.0
_last_spoken_text = ""

try:
    kokoro = Kokoro("kokoro-v0_19.onnx", "voices-v1.0.bin")
except Exception as e:
    print(f"Failed to load Kokoro: {e}")

tts_lock = threading.Lock()

def get_last_spoken_text():
    return _last_spoken_text

def get_last_speech_end_time():
    return _last_speech_end_time

def stop_speaking():
    global _stop_requested
    _stop_requested = True
    sd.stop()

def speak(text):
    global _speak_count, is_speaking, _last_spoken_text, _stop_requested
    _speak_count += 1
    is_speaking = True
    _stop_requested = False
    _last_spoken_text = text

    # Split into sentences so synthesis of sentence N+1 overlaps with playback of N
    parts = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    if not parts:
        parts = [text]

    def _speak():
        global _speak_count, is_speaking, _last_speech_end_time
        with tts_lock:
            _DONE = object()
            audio_q = _q.Queue(maxsize=2)   # buffer one sentence ahead

            def synth_worker():
                for i, part in enumerate(parts):
                    if _stop_requested:
                        break
                    try:
                        samples, sr = kokoro.create(part, voice=VOICE, speed=SPEED)
                        is_last = (i == len(parts) - 1)
                        # Long tail on last sentence prevents syllable cutoff
                        tail = np.zeros(int(sr * (0.4 if is_last else 0.08)), dtype=samples.dtype)
                        audio_q.put((np.concatenate([samples, tail]), sr))
                    except Exception as e:
                        print(f"Synth error: {e}")
                audio_q.put(_DONE)

            threading.Thread(target=synth_worker, daemon=True).start()

            try:
                while not _stop_requested:
                    item = audio_q.get()
                    if item is _DONE:
                        break
                    samples, sr = item
                    sd.play(samples, sr)
                    sd.wait()
            except Exception as e:
                print(f"TTS Playback Error: {e}")
            finally:
                _speak_count -= 1
                if _speak_count == 0:
                    is_speaking = False
                    _last_speech_end_time = time.time()

    threading.Thread(target=_speak, daemon=True).start()

import threading
import time
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro

VOICE = "am_onyx"    # deep American male — bm_george / bm_lewis / am_fenrir are other options
SPEED = 0.95         # slightly slower sounds more natural

_speak_count = 0
is_speaking = False
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
    sd.stop()

def speak(text):
    global _speak_count, is_speaking, _last_spoken_text
    _speak_count += 1
    is_speaking = True
    _last_spoken_text = text

    def _speak():
        global _speak_count, is_speaking, _last_speech_end_time
        with tts_lock:
            try:
                samples, sample_rate = kokoro.create(text, voice=VOICE, speed=SPEED)
                # Pad 400 ms of silence so the last syllable isn't clipped by the buffer
                tail = np.zeros(int(sample_rate * 0.4), dtype=samples.dtype)
                samples = np.concatenate([samples, tail])
                sd.play(samples, sample_rate)
                sd.wait()
            except Exception as e:
                print(f"TTS Error: {e}")
            finally:
                _speak_count -= 1
                if _speak_count == 0:
                    is_speaking = False
                    _last_speech_end_time = time.time()

    threading.Thread(target=_speak, daemon=True).start()

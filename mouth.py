import threading
import sounddevice as sd
from kokoro_onnx import Kokoro

# Global flag for the Mute/Listen logic
is_speaking = False 

# Load the model
try:
    # Ensure these files are in your folder: 'kokoro-v0_19.onnx' and 'voices-v1.0.bin'
    # Note: If you downloaded 'voices-v1.0.bin', use that filename below.
    kokoro = Kokoro("kokoro-v0_19.onnx", "voices-v1.0.bin")
except Exception as e:
    print(f"Failed to load Kokoro: {e}")

tts_lock = threading.Lock()

def speak(text):
    """Speaks text locally using Kokoro."""
    global is_speaking
    def _speak():
        global is_speaking
        with tts_lock:
            try:
                is_speaking = True # Mute mic
                samples, sample_rate = kokoro.create(text, voice="am_adam", speed=1.0)
                sd.play(samples, sample_rate)
                sd.wait()
            except Exception as e:
                print(f"TTS Error: {e}")
            finally:
                is_speaking = False # Unmute mic
    
    threading.Thread(target=_speak).start()
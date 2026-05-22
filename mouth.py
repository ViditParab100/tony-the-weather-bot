# mouth.py
import threading
import sounddevice as sd
from kokoro_onnx import Kokoro

# Load the model locally (it's only ~80MB)
# Ensure you have 'kokoro-v0_19.onnx' and 'voices.json' in your project folder
# You can download them from the official Kokoro-onnx repo
try:
    kokoro = Kokoro("kokoro-v0_19.onnx", "voices.json")
except Exception as e:
    print(f"Failed to load Kokoro: {e}")

tts_lock = threading.Lock()

def speak(text):
    """Speaks natural speech locally, instantly."""
    def _speak():
        with tts_lock:
            try:
                # Generate samples locally
                # 'af' is a natural sounding female voice, 'am' is male
                samples, sample_rate = kokoro.create(text, voice="am_adam", speed=1.0)
                
                # Play audio locally
                sd.play(samples, sample_rate)
                sd.wait()
            except Exception as e:
                print(f"TTS Error: {e}")
    
    threading.Thread(target=_speak).start()
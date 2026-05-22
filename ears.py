import io
import wave
from sarvamai import SarvamAI
from config import SARVAM_KEY

client = SarvamAI(api_subscription_key=SARVAM_KEY)

def transcribe_audio(audio_data):
    """Sends audio bytes to Sarvam STT and gets text."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(audio_data.get_wav_data())
    
    wav_io.seek(0)
    
    # Restricting to English (en-IN for Indian English context)
    response = client.speech_to_text.transcribe(
        file=wav_io, 
        model="saaras:v3",
        language_code="en-IN" 
    )
    return response.transcript
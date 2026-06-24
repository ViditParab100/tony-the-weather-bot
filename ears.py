import io
from sarvamai import SarvamAI
from config import SARVAM_KEY

client = SarvamAI(api_subscription_key=SARVAM_KEY)

def transcribe_audio(audio_data):
    # get_wav_data() returns a complete WAV file; resample to 16kHz/16-bit for Sarvam
    wav_io = io.BytesIO(audio_data.get_wav_data(convert_rate=16000, convert_width=2))
    response = client.speech_to_text.transcribe(
        file=wav_io,
        model="saaras:v3",
        language_code="en-IN"
    )
    return response.transcript

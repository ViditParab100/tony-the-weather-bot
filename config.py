import os
SARVAM_KEY = os.environ.get("SARVAM_API_KEY")
GROQ_KEY   = os.environ.get("GROQ_API_KEY")
LOCATION   = "Bengaluru"

# Switch between LLM backends: "groq" or "sarvam"
LLM_PROVIDER = "groq"
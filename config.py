import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file automatically

SARVAM_KEY   = os.environ.get("SARVAM_API_KEY")
GROQ_KEY     = os.environ.get("GROQ_API_KEY")
LOCATION     = "Bengaluru"

# Switch between LLM backends: "groq" or "sarvam"
LLM_PROVIDER = "groq"

# Zomato city slug — must match the city in Zomato's URL (e.g. "bangalore", "mumbai", "delhi")
ZOMATO_CITY  = "bangalore"

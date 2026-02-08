"""
Altiora AI — Configuration
===========================
All configuration loaded from environment variables.
Copy .env.example to .env and fill in your values.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration from environment variables"""

    # ─── Server Settings ─────────────────────────────────────────────────────
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "")  # Your ngrok URL

    # ─── Pipeline Mode ───────────────────────────────────────────────────────
    # Options: "mock" (testing), "modal" (production with Modal + ElevenLabs)
    PIPELINE_MODE: str = os.getenv("PIPELINE_MODE", "modal")

    # ─── Twilio Credentials ──────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

    # ─── ElevenLabs TTS ──────────────────────────────────────────────────────
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv(
        "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    # Voice IDs:
    # - Rachel (calm female): 21m00Tcm4TlvDq8ikWAM
    # - Domi (confident female): AZnzlk1XvdvUeBnXmlld
    # - Bella (soft female): EXAVITQu4vr4xnSDxMaL
    # - Josh (deep male): TxGEqnHWrfWFTfGW9XjX
    # - Arnold (crisp male): VR6AewLTigWG4xSOukaG

    # ─── Modal Endpoints ─────────────────────────────────────────────────────
    MODAL_STT_URL: str = os.getenv(
        "MODAL_STT_URL",
        "https://neet18101--altiora-stt-transcribe-audio.modal.run"
    )
    MODAL_LLM_URL: str = os.getenv(
        "MODAL_LLM_URL",
        "https://neet18101--altiora-llm-chat.modal.run"
    )

    # ─── LLM Settings ────────────────────────────────────────────────────────
    LLM_SYSTEM_PROMPT: str = os.getenv("LLM_SYSTEM_PROMPT", """You are a helpful AI assistant on a phone call. 
Keep your responses brief and conversational - this is a voice call, not a text chat.
Speak naturally, use short sentences, and be friendly.
Don't use bullet points, markdown, or special formatting.
If you don't understand something, politely ask for clarification.""")

    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "150"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))

    # ─── Audio Settings ──────────────────────────────────────────────────────
    AUDIO_SAMPLE_RATE_TWILIO: int = 8000   # Twilio uses 8kHz mulaw
    AUDIO_SAMPLE_RATE_STT: int = 16000     # Whisper expects 16kHz
    AUDIO_CHUNK_MS: int = 20               # Audio chunk duration in milliseconds

    # ─── Debugging ───────────────────────────────────────────────────────────
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_AUDIO: bool = os.getenv("LOG_AUDIO", "false").lower() == "true"

    # ─── SaaS Backend Integration ───────────────────────────────────────────
    SAAS_BACKEND_URL: str = os.getenv(
        "SAAS_BACKEND_URL", "http://localhost:5000")


# Create global config instance
config = Config()


# ─── Validation ──────────────────────────────────────────────────────────────
def validate_config():
    """Check if required configuration is present"""
    errors = []

    if config.PIPELINE_MODE == "modal":
        if not config.ELEVENLABS_API_KEY:
            errors.append("ELEVENLABS_API_KEY is required for modal mode")

    if not config.TWILIO_ACCOUNT_SID:
        errors.append("TWILIO_ACCOUNT_SID is required")
    if not config.TWILIO_AUTH_TOKEN:
        errors.append("TWILIO_AUTH_TOKEN is required")
    if not config.TWILIO_PHONE_NUMBER:
        errors.append("TWILIO_PHONE_NUMBER is required")

    if errors:
        print("⚠️  Configuration Errors:")
        for e in errors:
            print(f"   - {e}")
        print("\nPlease check your .env file!")
        return False

    return True


# Run validation on import (optional - uncomment if needed)
# validate_config()

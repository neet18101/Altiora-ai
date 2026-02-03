"""
Altiora AI Configuration
========================
Updated for Modal integration.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ─── Twilio ─────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

    # ─── Server ─────────────────────────────────────────────────────────────
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
    PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")

    # ─── Pipeline Mode ──────────────────────────────────────────────────────
    # "mock" = Fake AI responses (testing Twilio)
    # "modal" = Use Modal serverless GPUs
    # "runpod" = Use RunPod endpoints (legacy)
    PIPELINE_MODE = os.getenv("PIPELINE_MODE", "mock")

    # ─── Modal Configuration ────────────────────────────────────────────────
    # Your Modal workspace name (shown after 'modal setup')
    MODAL_WORKSPACE = os.getenv("MODAL_WORKSPACE", "neet18101")
    
    # Modal endpoints (auto-generated from workspace)
    # Format: https://{workspace}--{app-name}-{function}.modal.run
    MODAL_STT_URL = os.getenv(
        "MODAL_STT_URL", 
        f"https://{MODAL_WORKSPACE}--altiora-stt-transcribe.modal.run"
    )
    MODAL_TTS_URL = os.getenv(
        "MODAL_TTS_URL",
        f"https://{MODAL_WORKSPACE}--altiora-tts-synthesize.modal.run"
    )
    MODAL_LLM_URL = os.getenv(
        "MODAL_LLM_URL",
        f"https://{MODAL_WORKSPACE}--altiora-llm-chat.modal.run"
    )

    # ─── RunPod Endpoints (Legacy - keeping for reference) ──────────────────
    STT_API_URL = os.getenv("STT_API_URL", "http://localhost:8001")
    LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:8002/v1")
    TTS_API_URL = os.getenv("TTS_API_URL", "http://localhost:8003")

    # ─── LLM Settings ───────────────────────────────────────────────────────
    LLM_MODEL = os.getenv("LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
    LLM_SYSTEM_PROMPT = os.getenv(
        "LLM_SYSTEM_PROMPT",
        """You are a helpful AI phone assistant for a business. 
Keep your responses SHORT and conversational (1-2 sentences max).
Be natural like a real human on the phone - use casual language.
Never use bullet points, lists, or markdown formatting.
If you don't understand, ask for clarification politely.""",
    )
    
    # ─── Voice Settings ─────────────────────────────────────────────────────
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
    TTS_VOICE = os.getenv("TTS_VOICE", "default")  # or specific voice ID
    
    # ─── Audio Settings ─────────────────────────────────────────────────────
    SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "1.5"))  # seconds
    MIN_AUDIO_LENGTH = int(os.getenv("MIN_AUDIO_LENGTH", "3200"))  # bytes
    BARGE_IN_ENERGY_THRESHOLD = int(os.getenv("BARGE_IN_ENERGY_THRESHOLD", "500"))


config = Config()


# ─── Print config on import (for debugging) ─────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("ALTIORA AI CONFIGURATION")
    print("=" * 50)
    print(f"Pipeline Mode: {config.PIPELINE_MODE}")
    print(f"Modal Workspace: {config.MODAL_WORKSPACE}")
    print(f"Twilio Configured: {bool(config.TWILIO_ACCOUNT_SID)}")
    print()
    print("Modal Endpoints:")
    print(f"  STT: {config.MODAL_STT_URL}")
    print(f"  LLM: {config.MODAL_LLM_URL}")
    print(f"  TTS: {config.MODAL_TTS_URL}")
    print("=" * 50)

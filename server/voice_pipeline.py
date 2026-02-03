"""
Voice Pipeline Orchestrator
============================
Handles the full flow: Audio -> STT -> LLM -> TTS -> Audio

- STT: Modal (Whisper)
- LLM: Modal (Mistral)  
- TTS: Direct ElevenLabs API (no Modal needed!)
"""

import asyncio
import base64
import logging
import time
import subprocess
import tempfile
import os

import httpx

from audio_utils import pcm_to_wav_bytes, wav_bytes_to_pcm, resample
from config import config

logger = logging.getLogger(__name__)


class ConversationState:
    def __init__(self, system_prompt: str = None):
        self.system_prompt = system_prompt or config.LLM_SYSTEM_PROMPT
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.call_start_time = time.time()

    def add_user_message(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def add_assistant_message(self, text: str):
        self.messages.append({"role": "assistant", "content": text})

    def get_messages(self) -> list[dict]:
        return self.messages.copy()


class MockPipeline:
    RESPONSES = [
        "I understand. Let me help you with that.",
        "That's a great question.",
        "Is there anything else I can help you with?",
    ]

    def __init__(self):
        self.response_index = 0

    async def speech_to_text(self, audio_pcm: bytes) -> str:
        return "Hello, this is a test."

    async def generate_response(self, state: ConversationState, user_text: str) -> str:
        state.add_user_message(user_text)
        response = self.RESPONSES[self.response_index % len(self.RESPONSES)]
        self.response_index += 1
        state.add_assistant_message(response)
        return response

    async def text_to_speech(self, text: str) -> bytes:
        import math
        import struct
        sample_rate = 8000
        duration = max(1.0, len(text) * 0.06)
        samples = []
        for i in range(int(sample_rate * duration)):
            t = i / sample_rate
            amp = 8000 * max(0, 1 - t / duration)
            samples.append(struct.pack(
                "<h", int(amp * math.sin(2 * 3.14159 * 440 * t))))
        return b"".join(samples)


class ModalPipeline:
    """STT/LLM on Modal, TTS direct from ElevenLabs"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=120.0)

        # Modal endpoints
        self.stt_url = "https://neet18101--altiora-stt-transcribe-audio.modal.run"
        self.llm_url = "https://neet18101--altiora-llm-chat.modal.run"

        # ElevenLabs - Direct API (no Modal!)
        self.elevenlabs_key = "sk_2ff8836c7112d906956265b576f8ae9a28b4cfc64bee8767"
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel

        logger.info("✅ Pipeline: STT/LLM=Modal, TTS=ElevenLabs Direct")

    async def speech_to_text(self, audio_pcm_16k: bytes) -> str:
        start = time.time()
        wav_bytes = pcm_to_wav_bytes(audio_pcm_16k, sample_rate=16000)
        audio_b64 = base64.b64encode(wav_bytes).decode()

        try:
            r = await self.http_client.post(
                self.stt_url,
                json={"audio": audio_b64, "language": "en"},
            )
            r.raise_for_status()
            text = r.json().get("text", "").strip()
            logger.info(f"[STT] {time.time()-start:.2f}s: '{text}'")
            return text
        except Exception as e:
            logger.error(f"[STT] Error: {e}")
            return ""

    async def generate_response(self, state: ConversationState, user_text: str) -> str:
        start = time.time()
        state.add_user_message(user_text)

        try:
            r = await self.http_client.post(
                self.llm_url,
                json={"messages": state.get_messages(), "max_tokens": 150,
                      "temperature": 0.7},
            )
            r.raise_for_status()
            choices = r.json().get("choices", [])
            text = choices[0].get("message", {}).get(
                "content", "") if choices else ""
            text = text.strip() or "Sorry, could you repeat?"
            state.add_assistant_message(text)
            logger.info(f"[LLM] {time.time()-start:.2f}s: '{text}'")
            return text
        except Exception as e:
            logger.error(f"[LLM] Error: {e}")
            return "I'm having trouble. Please repeat."

    async def text_to_speech(self, text: str) -> bytes:
        """Direct ElevenLabs API - no Modal!"""
        start = time.time()

        try:
            r = await self.http_client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
                headers={"xi-api-key": self.elevenlabs_key,
                         "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                }
            )

            if r.status_code != 200:
                logger.error(f"[TTS] ElevenLabs error: {r.status_code}")
                return b""

            # Convert MP3 to PCM 8kHz
            mp3_bytes = r.content

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(mp3_bytes)
                mp3_path = f.name

            wav_path = mp3_path.replace(".mp3", ".wav")
            subprocess.run(["ffmpeg", "-y", "-i", mp3_path, "-ar", "8000", "-ac", "1", "-f", "wav", wav_path],
                           capture_output=True, timeout=10)

            with open(wav_path, "rb") as f:
                pcm_data, _ = wav_bytes_to_pcm(f.read())

            os.unlink(mp3_path)
            os.unlink(wav_path)

            logger.info(
                f"[TTS] ElevenLabs {time.time()-start:.2f}s, {len(pcm_data)} bytes")
            return pcm_data

        except Exception as e:
            logger.error(f"[TTS] Error: {e}")
            return b""

    async def close(self):
        await self.http_client.aclose()


def create_pipeline():
    mode = config.PIPELINE_MODE.lower()
    if mode == "mock":
        logger.info("🎭 MOCK mode")
        return MockPipeline()
    elif mode == "modal":
        logger.info("🚀 MODAL mode (TTS=ElevenLabs Direct)")
        return ModalPipeline()
    else:
        return MockPipeline()

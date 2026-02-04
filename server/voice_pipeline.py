"""
Voice Pipeline Orchestrator
============================
Handles the full flow: Audio -> STT -> LLM -> TTS -> Audio

- STT: RunPod (Whisper)
- LLM: RunPod (Llama 3.1)  
- TTS: ElevenLabs SDK
"""

import asyncio
import base64
import logging
import time
import subprocess
import tempfile
import os

import httpx
from elevenlabs import ElevenLabs

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
    """Mock pipeline for testing without external services"""

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


class RunPodPipeline:
    """Production Pipeline: STT/LLM on RunPod, TTS via ElevenLabs SDK"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=120.0)

        # RunPod endpoints
        self.stt_url = config.MODAL_STT_URL  # Points to RunPod now
        self.llm_url = config.MODAL_LLM_URL  # Points to RunPod now

        # ElevenLabs SDK client
        self.elevenlabs_key = config.ELEVENLABS_API_KEY
        self.voice_id = config.ELEVENLABS_VOICE_ID
        self.elevenlabs_client = None

        if not self.elevenlabs_key:
            logger.warning("⚠️ ELEVENLABS_API_KEY not set in .env!")
        else:
            self.elevenlabs_client = ElevenLabs(api_key=self.elevenlabs_key)

        logger.info(f"✅ Pipeline Ready:")
        logger.info(f"   STT: {self.stt_url}")
        logger.info(f"   LLM: {self.llm_url}")
        logger.info(f"   TTS: ElevenLabs (Voice: {self.voice_id})")

    async def speech_to_text(self, audio_pcm_16k: bytes) -> str:
        """Convert speech to text using RunPod Whisper"""
        start = time.time()
        wav_bytes = pcm_to_wav_bytes(audio_pcm_16k, sample_rate=16000)
        audio_b64 = base64.b64encode(wav_bytes).decode()

        try:
            r = await self.http_client.post(
                self.stt_url,
                json={"audio": audio_b64, "language": "en"},
            )
            r.raise_for_status()
            response_data = r.json()
            text = response_data.get("text", "").strip()
            error = response_data.get("error", "")

            if error:
                logger.error(f"[STT] Server error: {error}")
                return ""

            logger.info(f"[STT] {time.time()-start:.2f}s: '{text}'")
            return text
        except Exception as e:
            logger.error(f"[STT] Error: {e}")
            return ""

    async def generate_response(self, state: ConversationState, user_text: str) -> str:
        """Generate AI response using RunPod Llama 3.1"""
        start = time.time()
        state.add_user_message(user_text)

        try:
            r = await self.http_client.post(
                self.llm_url,
                json={
                    "messages": state.get_messages(),
                    "max_tokens": config.LLM_MAX_TOKENS,
                    "temperature": config.LLM_TEMPERATURE
                },
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
        """Convert text to speech using ElevenLabs SDK"""
        start = time.time()

        if not self.elevenlabs_client:
            logger.error("[TTS] ElevenLabs client not initialized!")
            return b""

        try:
            # Run sync SDK call in thread pool
            loop = asyncio.get_event_loop()
            audio_generator = await loop.run_in_executor(
                None,
                lambda: self.elevenlabs_client.text_to_speech.convert(
                    text=text,
                    voice_id=self.voice_id,
                    model_id="eleven_flash_v2_5",
                    output_format="mp3_44100_128",
                )
            )

            # Collect audio chunks
            mp3_bytes = b""
            for chunk in audio_generator:
                mp3_bytes += chunk

            if not mp3_bytes:
                logger.error("[TTS] No audio generated!")
                return b""

            # Save MP3 to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(mp3_bytes)
                mp3_path = f.name

            # Convert to WAV 8kHz for Twilio
            wav_path = mp3_path.replace(".mp3", ".wav")

            result = subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, "-ar",
                    "8000", "-ac", "1", "-f", "wav", wav_path],
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"[TTS] ffmpeg error: {result.stderr.decode()}")
                os.unlink(mp3_path)
                return b""

            # Read PCM data
            with open(wav_path, "rb") as f:
                pcm_data, _ = wav_bytes_to_pcm(f.read())

            # Cleanup temp files
            os.unlink(mp3_path)
            os.unlink(wav_path)

            logger.info(
                f"[TTS] ElevenLabs {time.time()-start:.2f}s, {len(pcm_data)} bytes")
            return pcm_data

        except Exception as e:
            logger.error(f"[TTS] Error: {e}")
            return b""

    async def close(self):
        """Cleanup HTTP client"""
        await self.http_client.aclose()


def create_pipeline():
    """Factory function to create appropriate pipeline based on config"""
    mode = config.PIPELINE_MODE.lower()

    if mode == "mock":
        logger.info("🎭 MOCK mode - Using test responses")
        return MockPipeline()
    elif mode == "modal" or mode == "runpod":
        logger.info("🚀 RUNPOD mode - Production pipeline")
        return RunPodPipeline()
    else:
        logger.warning(f"⚠️ Unknown mode '{mode}', defaulting to MOCK")
        return MockPipeline()

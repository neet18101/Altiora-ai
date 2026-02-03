"""
Twilio WebSocket Handler
========================
Handles the bidirectional audio stream between Twilio and our AI pipeline.

Flow:
  1. Twilio opens WebSocket when a call connects
  2. We receive audio chunks (mulaw 8kHz, base64)
  3. Buffer audio, detect speech end (VAD)
  4. Send buffered audio to STT -> LLM -> TTS
  5. Stream TTS audio back to Twilio
  6. Handle barge-in (caller interrupts AI response)

Twilio Media Stream events:
  - "connected": WebSocket connected
  - "start": Stream started (contains streamSid)
  - "media": Audio data (base64 mulaw payload)
  - "stop": Stream ended
"""

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field

from fastapi import WebSocket

from audio_utils import (
    base64_mulaw_to_pcm_16k,
    chunk_audio,
    mulaw_to_pcm16,
    pcm_16k_to_mulaw_8k,
    pcm_to_base64_mulaw,
    resample,
)
from voice_pipeline import ConversationState, create_pipeline

logger = logging.getLogger(__name__)


@dataclass
class CallSession:
    """State for a single active call."""
    call_sid: str = ""
    stream_sid: str = ""
    audio_buffer: bytearray = field(default_factory=bytearray)
    conversation: ConversationState = field(default_factory=ConversationState)
    is_speaking: bool = False           # Is the AI currently sending audio?
    is_processing: bool = False         # Is the pipeline currently processing?
    last_audio_time: float = 0.0        # Timestamp of last received audio
    silence_threshold: float = 1.5      # Seconds of silence before processing
    min_audio_length: int = 3200        # Min PCM bytes before processing (~100ms at 16kHz)
    greeting_sent: bool = False


class TwilioWebSocketHandler:
    """Manages a single Twilio Media Stream WebSocket connection."""

    def __init__(self):
        self.pipeline = create_pipeline()

    async def handle(self, websocket: WebSocket):
        """Main handler for the Twilio WebSocket connection."""
        await websocket.accept()
        session = CallSession()

        logger.info("WebSocket connection accepted")

        try:
            # Start the silence detection loop
            silence_task = asyncio.create_task(
                self._silence_detector(websocket, session)
            )

            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_text(), timeout=60.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("WebSocket timeout — closing")
                    break

                data = json.loads(message)
                event = data.get("event")

                if event == "connected":
                    logger.info("Twilio Media Stream connected")

                elif event == "start":
                    session.stream_sid = data["start"]["streamSid"]
                    session.call_sid = data["start"]["callSid"]
                    logger.info(
                        f"Stream started — callSid={session.call_sid}, "
                        f"streamSid={session.stream_sid}"
                    )
                    # Send greeting on first connection
                    if not session.greeting_sent:
                        session.greeting_sent = True
                        asyncio.create_task(
                            self._send_greeting(websocket, session)
                        )

                elif event == "media":
                    await self._handle_media(websocket, session, data)

                elif event == "stop":
                    logger.info("Stream stopped")
                    break

        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            silence_task.cancel()
            logger.info(f"Call ended — callSid={session.call_sid}")

    async def _handle_media(self, websocket: WebSocket, session: CallSession, data: dict):
        """Process incoming audio from Twilio."""
        payload = data["media"]["payload"]

        # If AI is currently speaking and we receive audio, that's a barge-in
        if session.is_speaking:
            # Check if the incoming audio has actual speech (not just silence)
            mulaw_bytes = base64.b64decode(payload)
            pcm = mulaw_to_pcm16(mulaw_bytes)
            energy = sum(abs(int.from_bytes(pcm[i:i+2], 'little', signed=True))
                        for i in range(0, min(len(pcm), 640), 2)) / max(1, min(len(pcm), 640) // 2)

            if energy > 500:  # Threshold for speech vs silence
                logger.info("[BARGE-IN] Caller interrupted — stopping AI audio")
                session.is_speaking = False
                # Clear the audio buffer to start fresh
                session.audio_buffer.clear()
                # Send clear message to stop Twilio's audio playback
                await self._send_clear(websocket, session)

        # Convert Twilio mulaw to PCM 16kHz and buffer it
        pcm_16k = base64_mulaw_to_pcm_16k(payload)
        session.audio_buffer.extend(pcm_16k)
        session.last_audio_time = time.time()

    async def _silence_detector(self, websocket: WebSocket, session: CallSession):
        """
        Background task: detect when caller stops speaking.
        After silence_threshold seconds of no new audio, process the buffer.
        """
        while True:
            await asyncio.sleep(0.2)  # Check every 200ms

            if session.is_processing or session.is_speaking:
                continue

            if len(session.audio_buffer) < session.min_audio_length:
                continue

            if session.last_audio_time == 0:
                continue

            elapsed = time.time() - session.last_audio_time
            if elapsed >= session.silence_threshold:
                # Silence detected — process the buffered audio
                audio_data = bytes(session.audio_buffer)
                session.audio_buffer.clear()
                session.last_audio_time = 0

                asyncio.create_task(
                    self._process_and_respond(websocket, session, audio_data)
                )

    async def _process_and_respond(
        self, websocket: WebSocket, session: CallSession, audio_pcm_16k: bytes
    ):
        """Run the full pipeline: STT -> LLM -> TTS -> stream back."""
        if session.is_processing:
            return

        session.is_processing = True
        start_time = time.time()

        try:
            # ── Step 1: Speech to Text ──
            logger.info(f"[PIPELINE] Processing {len(audio_pcm_16k)} bytes of audio")
            transcript = await self.pipeline.speech_to_text(audio_pcm_16k)

            if not transcript or len(transcript.strip()) < 2:
                logger.info("[PIPELINE] Empty transcript — ignoring")
                return

            logger.info(f"[PIPELINE] Caller said: '{transcript}'")

            # ── Step 2: LLM Response ──
            response_text = await self.pipeline.generate_response(
                session.conversation, transcript
            )
            logger.info(f"[PIPELINE] AI responds: '{response_text}'")

            # ── Step 3: Text to Speech ──
            tts_pcm = await self.pipeline.text_to_speech(response_text)

            if not tts_pcm:
                logger.warning("[PIPELINE] TTS returned empty audio")
                return

            # ── Step 4: Stream audio back to Twilio ──
            total_time = time.time() - start_time
            logger.info(f"[PIPELINE] Total processing time: {total_time:.2f}s")

            await self._stream_audio_to_twilio(websocket, session, tts_pcm)

        except Exception as e:
            logger.error(f"[PIPELINE] Error: {e}", exc_info=True)
        finally:
            session.is_processing = False

    async def _stream_audio_to_twilio(
        self, websocket: WebSocket, session: CallSession, pcm_audio: bytes,
        input_rate: int = 8000
    ):
        """
        Convert PCM audio to mulaw and stream it back to Twilio in chunks.
        """
        session.is_speaking = True

        try:
            # Convert to mulaw 8kHz
            mulaw_audio = pcm_16k_to_mulaw_8k(pcm_audio, input_rate=input_rate)

            # Split into 20ms chunks (640 bytes for mulaw 8kHz)
            chunks = chunk_audio(mulaw_audio, chunk_size=640)

            for chunk in chunks:
                if not session.is_speaking:
                    # Barge-in happened — stop sending
                    logger.info("[STREAM] Barge-in detected — stopping playback")
                    break

                payload = base64.b64encode(chunk).decode("ascii")
                media_message = {
                    "event": "media",
                    "streamSid": session.stream_sid,
                    "media": {"payload": payload},
                }
                await websocket.send_text(json.dumps(media_message))

                # Pace the audio at real-time speed (20ms per chunk)
                await asyncio.sleep(0.02)

        finally:
            session.is_speaking = False

    async def _send_greeting(self, websocket: WebSocket, session: CallSession):
        """Send an initial greeting when the call connects."""
        await asyncio.sleep(0.5)  # Small delay for stream to stabilize

        greeting = "Hello! Thanks for calling. How can I help you today?"
        logger.info(f"[GREETING] Sending: '{greeting}'")

        session.conversation.add_assistant_message(greeting)

        try:
            tts_audio = await self.pipeline.text_to_speech(greeting)
            if tts_audio:
                await self._stream_audio_to_twilio(websocket, session, tts_audio)
        except Exception as e:
            logger.error(f"[GREETING] Error: {e}")

    async def _send_clear(self, websocket: WebSocket, session: CallSession):
        """Tell Twilio to stop playing any queued audio."""
        clear_message = {
            "event": "clear",
            "streamSid": session.stream_sid,
        }
        try:
            await websocket.send_text(json.dumps(clear_message))
        except Exception:
            pass

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
"""

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field

import httpx
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
from config import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK CLIENT - Send events to SaaS Backend
# ═══════════════════════════════════════════════════════════════════════════════
class WebhookClient:
    """Send call events to SaaS backend for logging."""

    def __init__(self):
        self.base_url = config.SAAS_BACKEND_URL
        self.client = httpx.AsyncClient(timeout=10.0)
        logger.info(f"📡 Webhook client ready: {self.base_url}")

    async def call_started(self, business_id: str, agent_id: str, direction: str,
                           from_number: str, to_number: str, twilio_call_sid: str) -> str:
        """Notify backend when call starts. Returns call_id."""
        try:
            r = await self.client.post(
                f"{self.base_url}/api/webhooks/call-started",
                json={
                    "business_id": business_id,
                    "agent_id": agent_id,
                    "direction": direction,
                    "from_number": from_number,
                    "to_number": to_number,
                    "twilio_call_sid": twilio_call_sid,
                }
            )
            data = r.json()
            call_id = data.get("data", {}).get("call_id", "")
            logger.info(f"[WEBHOOK] ✅ call-started: call_id={call_id}")
            return call_id
        except Exception as e:
            logger.error(f"[WEBHOOK] ❌ call-started error: {e}")
            return ""

    async def call_ended(self, call_id: str, duration_secs: int, outcome: str = "completed",
                         sentiment: str = None, summary: str = None):
        """Notify backend when call ends."""
        if not call_id:
            return
        try:
            await self.client.post(
                f"{self.base_url}/api/webhooks/call-ended",
                json={
                    "call_id": call_id,
                    "duration_secs": duration_secs,
                    "outcome": outcome,
                    "sentiment": sentiment,
                    "summary": summary,
                }
            )
            logger.info(f"[WEBHOOK] ✅ call-ended: {duration_secs}s")
        except Exception as e:
            logger.error(f"[WEBHOOK] ❌ call-ended error: {e}")

    async def transcript(self, call_id: str, speaker: str, message: str,
                         timestamp_secs: float = None, stt_duration_ms: int = None,
                         llm_duration_ms: int = None, tts_duration_ms: int = None):
        """Send transcript line to backend."""
        if not call_id:
            return
        try:
            await self.client.post(
                f"{self.base_url}/api/webhooks/transcript",
                json={
                    "call_id": call_id,
                    "speaker": speaker,
                    "message": message,
                    "timestamp_secs": timestamp_secs,
                    "stt_duration_ms": stt_duration_ms,
                    "llm_duration_ms": llm_duration_ms,
                    "tts_duration_ms": tts_duration_ms,
                }
            )
            logger.debug(f"[WEBHOOK] transcript: {speaker}: {message[:50]}...")
        except Exception as e:
            logger.error(f"[WEBHOOK] ❌ transcript error: {e}")

    async def close(self):
        await self.client.aclose()


# Global webhook client
webhook_client = WebhookClient()


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
    speech_started: bool = False        # Has caller started speaking?

    # ═══ TUNED PARAMETERS ═══
    # Seconds of silence before processing (was 1.0)
    silence_threshold: float = 0.7
    # Min PCM bytes (~375ms at 16kHz) (was 16000)
    min_audio_length: int = 12000
    # Energy level to detect speech (was 300)
    speech_energy_threshold: int = 150

    greeting_sent: bool = False
    audio_chunks_received: int = 0      # Debug counter

    # ═══ WEBHOOK TRACKING ═══
    call_id: str = ""                   # Returned from SaaS backend
    business_id: str = ""               # Set by main.py
    agent_id: str = ""                  # Set by main.py
    from_number: str = ""               # Caller number
    to_number: str = ""                 # Called number
    call_start_time: float = 0.0        # For duration calc
    greeting_message: str = "Hello! Thanks for calling. How can I help you today?"


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
                    session.call_start_time = time.time()

                    # Get from/to from start data if available
                    start_data = data.get("start", {})
                    custom_params = start_data.get("customParameters", {})
                    session.business_id = custom_params.get("business_id", "")
                    session.agent_id = custom_params.get("agent_id", "")
                    session.from_number = start_data.get("from", "")
                    session.to_number = start_data.get("to", "")

                    # Extract agent's system prompt (URL decoded)
                    import urllib.parse
                    system_prompt = custom_params.get("system_prompt", "")
                    if system_prompt:
                        system_prompt = urllib.parse.unquote(system_prompt)
                        session.conversation = ConversationState(
                            system_prompt=system_prompt)
                        logger.info(
                            f"Using custom system prompt: {system_prompt[:100]}...")

                    # Extract greeting message
                    greeting_msg = custom_params.get("greeting_message", "")
                    if greeting_msg:
                        session.greeting_message = urllib.parse.unquote(
                            greeting_msg)
                        logger.info(
                            f"Using custom greeting: {session.greeting_message[:50]}...")

                    agent_name = custom_params.get(
                        "agent_name", "AI Assistant")

                    logger.info(
                        f"Stream started — callSid={session.call_sid}, "
                        f"streamSid={session.stream_sid}, agent={agent_name}"
                    )

                    # Notify SaaS backend of call start
                    # If business_id is passed via params, it's an outbound call
                    call_direction = "outbound" if session.business_id else "inbound"
                    call_id = await webhook_client.call_started(
                        business_id=session.business_id,
                        agent_id=session.agent_id,
                        direction=call_direction,
                        from_number=session.from_number,
                        to_number=session.to_number,
                        twilio_call_sid=session.call_sid,
                    )
                    session.call_id = call_id

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

            # Calculate call duration and notify backend
            duration_secs = int(
                time.time() - session.call_start_time) if session.call_start_time > 0 else 0
            await webhook_client.call_ended(
                call_id=session.call_id,
                duration_secs=duration_secs,
                outcome="completed",
            )

            logger.info(
                f"Call ended — callSid={session.call_sid}, duration={duration_secs}s")

    async def _handle_media(self, websocket: WebSocket, session: CallSession, data: dict):
        """Process incoming audio from Twilio."""
        payload = data["media"]["payload"]

        # Decode audio
        mulaw_bytes = base64.b64decode(payload)
        pcm = mulaw_to_pcm16(mulaw_bytes)

        # Calculate energy level
        energy = self._calculate_energy(pcm)

        session.audio_chunks_received += 1

        # Log every 50 chunks (~1 second of audio)
        if session.audio_chunks_received % 50 == 0:
            logger.debug(
                f"[AUDIO] Chunks={session.audio_chunks_received}, buffer={len(session.audio_buffer)} bytes, energy={energy:.0f}")

        # If AI is currently speaking and we receive loud audio, that's a barge-in
        if session.is_speaking:
            if energy > session.speech_energy_threshold:
                logger.info(
                    f"[BARGE-IN] Caller interrupted — energy={energy:.0f}")
                session.is_speaking = False
                session.audio_buffer.clear()
                await self._send_clear(websocket, session)
                return

        # Detect if caller started speaking
        if energy > session.speech_energy_threshold:
            if not session.speech_started:
                logger.info(f"[VAD] 🎤 Speech started — energy={energy:.0f}")
                session.speech_started = True
            session.last_audio_time = time.time()

        # Convert Twilio mulaw to PCM 16kHz and buffer it
        pcm_16k = base64_mulaw_to_pcm_16k(payload)
        session.audio_buffer.extend(pcm_16k)

    def _calculate_energy(self, pcm_bytes: bytes) -> float:
        """Calculate audio energy level for VAD."""
        if len(pcm_bytes) < 2:
            return 0

        total = 0
        count = 0
        for i in range(0, min(len(pcm_bytes), 640), 2):
            if i + 1 < len(pcm_bytes):
                sample = int.from_bytes(
                    pcm_bytes[i:i+2], 'little', signed=True)
                total += abs(sample)
                count += 1

        return total / max(1, count)

    async def _silence_detector(self, websocket: WebSocket, session: CallSession):
        """
        Background task: detect when caller stops speaking.
        After silence_threshold seconds of no speech, process the buffer.
        """
        while True:
            await asyncio.sleep(0.1)  # Check every 100ms

            # Skip if already processing or speaking
            if session.is_processing or session.is_speaking:
                continue

            # Skip if no speech detected yet
            if not session.speech_started:
                continue

            # Skip if buffer too small
            if len(session.audio_buffer) < session.min_audio_length:
                continue

            # Skip if no audio timestamp
            if session.last_audio_time == 0:
                continue

            # Check for silence
            elapsed = time.time() - session.last_audio_time

            if elapsed >= session.silence_threshold:
                buffer_size = len(session.audio_buffer)
                logger.info(
                    f"[VAD] 🔇 Silence detected — {elapsed:.2f}s, buffer={buffer_size} bytes")

                # Grab the audio and reset
                audio_data = bytes(session.audio_buffer)
                session.audio_buffer.clear()
                session.last_audio_time = 0
                session.speech_started = False

                # Process in background
                asyncio.create_task(
                    self._process_and_respond(websocket, session, audio_data)
                )

    async def _process_and_respond(
        self, websocket: WebSocket, session: CallSession, audio_pcm_16k: bytes
    ):
        """Run the full pipeline: STT -> LLM -> TTS -> stream back."""
        if session.is_processing:
            logger.warning("[PIPELINE] Already processing — skipping")
            return

        session.is_processing = True
        start_time = time.time()
        stt_duration_ms = 0
        llm_duration_ms = 0
        tts_duration_ms = 0

        try:
            # ── Step 1: Speech to Text ──
            stt_start = time.time()
            logger.info(
                f"[PIPELINE] 🎤 Processing {len(audio_pcm_16k)} bytes of audio...")
            transcript = await self.pipeline.speech_to_text(audio_pcm_16k)
            stt_duration_ms = int((time.time() - stt_start) * 1000)

            if not transcript or len(transcript.strip()) < 2:
                logger.info("[PIPELINE] ❌ Empty transcript — ignoring")
                return

            logger.info(f"[PIPELINE] 📝 Caller said: '{transcript}'")

            # Send caller transcript to backend
            timestamp_secs = time.time() - session.call_start_time
            await webhook_client.transcript(
                call_id=session.call_id,
                speaker="caller",
                message=transcript,
                timestamp_secs=timestamp_secs,
                stt_duration_ms=stt_duration_ms,
            )

            # ── Step 2: LLM Response ──
            llm_start = time.time()
            logger.info("[PIPELINE] 🤖 Generating AI response...")
            response_text = await self.pipeline.generate_response(
                session.conversation, transcript
            )
            llm_duration_ms = int((time.time() - llm_start) * 1000)
            logger.info(f"[PIPELINE] 💬 AI responds: '{response_text}'")

            # ── Step 3: Text to Speech ──
            tts_start = time.time()
            logger.info("[PIPELINE] 🔊 Generating speech...")
            tts_pcm = await self.pipeline.text_to_speech(response_text)
            tts_duration_ms = int((time.time() - tts_start) * 1000)

            if not tts_pcm:
                logger.warning("[PIPELINE] ❌ TTS returned empty audio")
                return

            # Send AI response transcript to backend
            timestamp_secs = time.time() - session.call_start_time
            await webhook_client.transcript(
                call_id=session.call_id,
                speaker="agent",
                message=response_text,
                timestamp_secs=timestamp_secs,
                stt_duration_ms=stt_duration_ms,
                llm_duration_ms=llm_duration_ms,
                tts_duration_ms=tts_duration_ms,
            )

            # ── Step 4: Stream audio back to Twilio ──
            total_time = time.time() - start_time
            logger.info(f"[PIPELINE] ✅ Total time: {total_time:.2f}s")
            logger.info(
                f"[PIPELINE] 📤 Streaming {len(tts_pcm)} bytes to caller...")

            await self._stream_audio_to_twilio(websocket, session, tts_pcm)

        except Exception as e:
            logger.error(f"[PIPELINE] ❌ Error: {e}", exc_info=True)
        finally:
            session.is_processing = False

    async def _stream_audio_to_twilio(
        self, websocket: WebSocket, session: CallSession, pcm_audio: bytes,
        input_rate: int = 8000
    ):
        """Convert PCM audio to mulaw and stream it back to Twilio in chunks."""
        session.is_speaking = True

        try:
            # Convert to mulaw 8kHz
            mulaw_audio = pcm_16k_to_mulaw_8k(pcm_audio, input_rate=input_rate)

            # Split into 20ms chunks (640 bytes for mulaw 8kHz = 80ms)
            chunks = chunk_audio(mulaw_audio, chunk_size=640)

            logger.info(f"[STREAM] 📤 Sending {len(chunks)} audio chunks...")

            for i, chunk in enumerate(chunks):
                if not session.is_speaking:
                    logger.info(
                        f"[STREAM] Barge-in at chunk {i}/{len(chunks)} — stopping")
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

            logger.info("[STREAM] ✅ Audio streaming complete")

        except Exception as e:
            logger.error(f"[STREAM] Error: {e}")
        finally:
            session.is_speaking = False

    async def _send_greeting(self, websocket: WebSocket, session: CallSession):
        """Send an initial greeting when the call connects."""
        await asyncio.sleep(0.5)  # Small delay for stream to stabilize

        greeting = session.greeting_message
        logger.info(f"[GREETING] 👋 Sending: '{greeting}'")

        session.conversation.add_assistant_message(greeting)

        try:
            tts_audio = await self.pipeline.text_to_speech(greeting)
            if tts_audio:
                await self._stream_audio_to_twilio(websocket, session, tts_audio)
                logger.info("[GREETING] ✅ Greeting sent successfully")

                # Clear buffer after greeting to avoid echo/noise
                await asyncio.sleep(0.3)
                session.audio_buffer.clear()
                session.speech_started = False
                session.last_audio_time = 0
                logger.info("[GREETING] 🧹 Buffer cleared after greeting")
            else:
                logger.error("[GREETING] ❌ TTS failed")
        except Exception as e:
            logger.error(f"[GREETING] ❌ Error: {e}")

    async def _send_clear(self, websocket: WebSocket, session: CallSession):
        """Tell Twilio to stop playing any queued audio."""
        clear_message = {
            "event": "clear",
            "streamSid": session.stream_sid,
        }
        try:
            await websocket.send_text(json.dumps(clear_message))
            logger.info("[CLEAR] 🛑 Sent clear to Twilio")
        except Exception:
            pass

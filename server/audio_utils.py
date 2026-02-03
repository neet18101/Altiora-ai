"""
Audio utilities for converting between Twilio's mulaw format and PCM/WAV.

Twilio Media Streams sends audio as:
  - Encoding: mulaw (G.711 μ-law)
  - Sample rate: 8000 Hz
  - Channels: mono
  - Payload: base64-encoded

Whisper (STT) expects:
  - 16-bit PCM WAV, 16000 Hz mono

TTS output needs to be converted back to:
  - mulaw, 8000 Hz mono, base64-encoded
"""

import audioop
import base64
import io
import struct
import wave


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Convert mulaw audio bytes to 16-bit PCM."""
    return audioop.ulaw2lin(mulaw_bytes, 2)


def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Convert 16-bit PCM audio bytes to mulaw."""
    return audioop.lin2ulaw(pcm_bytes, 2)


def resample(pcm_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample 16-bit PCM audio from one sample rate to another."""
    if from_rate == to_rate:
        return pcm_bytes
    converted, _ = audioop.ratecv(pcm_bytes, 2, 1, from_rate, to_rate, None)
    return converted


def mulaw_8k_to_pcm_16k(mulaw_bytes: bytes) -> bytes:
    """Convert Twilio mulaw 8kHz to PCM 16-bit 16kHz (for Whisper)."""
    pcm_8k = mulaw_to_pcm16(mulaw_bytes)
    pcm_16k = resample(pcm_8k, 8000, 16000)
    return pcm_16k


def pcm_16k_to_mulaw_8k(pcm_bytes: bytes, input_rate: int = 16000) -> bytes:
    """Convert PCM audio to Twilio mulaw 8kHz format."""
    pcm_8k = resample(pcm_bytes, input_rate, 8000)
    return pcm16_to_mulaw(pcm_8k)


def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw PCM bytes into a WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def wav_bytes_to_pcm(wav_bytes: bytes) -> tuple[bytes, int]:
    """Extract raw PCM data and sample rate from WAV bytes."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        sample_rate = wf.getframerate()
        pcm_data = wf.readframes(wf.getnframes())
    return pcm_data, sample_rate


def base64_mulaw_to_pcm_16k(base64_payload: str) -> bytes:
    """Decode Twilio's base64 mulaw payload to PCM 16kHz."""
    mulaw_bytes = base64.b64decode(base64_payload)
    return mulaw_8k_to_pcm_16k(mulaw_bytes)


def pcm_to_base64_mulaw(pcm_bytes: bytes, input_rate: int = 16000) -> str:
    """Convert PCM audio to Twilio-ready base64 mulaw."""
    mulaw_bytes = pcm_16k_to_mulaw_8k(pcm_bytes, input_rate)
    return base64.b64encode(mulaw_bytes).decode("ascii")


def chunk_audio(audio_bytes: bytes, chunk_size: int = 640) -> list[bytes]:
    """
    Split audio bytes into chunks for streaming back to Twilio.
    Default chunk_size=640 bytes = 20ms of mulaw 8kHz audio.
    Twilio expects 20ms chunks.
    """
    chunks = []
    for i in range(0, len(audio_bytes), chunk_size):
        chunk = audio_bytes[i : i + chunk_size]
        if len(chunk) < chunk_size:
            # Pad last chunk with silence (mulaw silence = 0xFF)
            chunk = chunk + b"\xff" * (chunk_size - len(chunk))
        chunks.append(chunk)
    return chunks

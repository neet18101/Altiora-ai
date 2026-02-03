"""
Modal STT Service - Faster Whisper
===================================
Serverless Speech-to-Text using faster-whisper on Modal GPU.

Usage:
    modal deploy modal_app/stt.py
"""

import modal

# ─── Modal App Setup ────────────────────────────────────────────────────────
app = modal.App("altiora-stt")

# Docker image with faster-whisper
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "faster-whisper==1.0.3",
        "numpy",
        "fastapi[standard]",
    )
)
# Create a volume to cache the model
model_cache = modal.Volume.from_name("whisper-cache", create_if_missing=True)


# ─── STT Class ──────────────────────────────────────────────────────────────
@app.cls(
    image=image,
    gpu="T4",
    timeout=60,
    scaledown_window=300,
    volumes={"/root/.cache": model_cache},
)
class WhisperSTT:
    @modal.enter()
    def load_model(self):
        """Load model when container starts."""
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            "base",
            device="cuda",
            compute_type="float16",
        )
        print("✅ Whisper model loaded!")

    @modal.method()
    def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict:
        """
        Transcribe audio bytes to text.
        """
        import tempfile
        import time

        start = time.time()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            f.write(audio_bytes)
            f.flush()

            segments, info = self.model.transcribe(
                f.name,
                language=language,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            text = " ".join(segment.text.strip() for segment in segments)

        elapsed = time.time() - start

        return {
            "text": text,
            "language": info.language,
            "duration": elapsed,
            "audio_duration": info.duration,
        }


# ─── Web Endpoint ───────────────────────────────────────────────────────────
@app.function(
    image=image,
    gpu="T4",
    timeout=60,
    scaledown_window=300,
    volumes={"/root/.cache": model_cache},
)
@modal.fastapi_endpoint(method="POST")
async def transcribe_audio(request: dict):
    """
    HTTP endpoint for transcription.

    POST /transcribe_audio
    Body: {"audio": "<base64>", "language": "en"}
    """
    from faster_whisper import WhisperModel
    import tempfile
    import time
    import base64

    audio_b64 = request.get("audio", "")
    language = request.get("language", "en")

    if not audio_b64:
        return {"text": "", "error": "No audio provided"}

    audio_bytes = base64.b64decode(audio_b64)

    model = WhisperModel("base", device="cuda", compute_type="float16")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
        f.write(audio_bytes)
        f.flush()

        segments, info = model.transcribe(
            f.name,
            language=language if language != "auto" else None,
            beam_size=5,
            vad_filter=True,
        )

        text = " ".join(segment.text.strip() for segment in segments)

    return {"text": text, "language": info.language}


# ─── Local Testing ──────────────────────────────────────────────────────────
@app.local_entrypoint()
def main():
    print("Testing Whisper STT...")
    print("✅ STT service ready!")
    print("\nTo deploy: modal deploy modal_app/stt.py")

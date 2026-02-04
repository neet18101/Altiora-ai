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
        "requests",
        "fastapi[standard]",
    )
)

# ─── Web Endpoint (No Volume - Model downloads fresh each cold start) ───────


@app.function(
    image=image,
    gpu="T4",
    timeout=120,
    scaledown_window=300,
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
    import base64
    import os

    audio_b64 = request.get("audio", "")
    language = request.get("language", "en")

    if not audio_b64:
        return {"text": "", "error": "No audio provided"}

    try:
        audio_bytes = base64.b64decode(audio_b64)

        # Load model (cached in container memory during warm period)
        model = WhisperModel(
            "base",
            device="cuda",
            compute_type="float16",
        )

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

    except Exception as e:
        return {"text": "", "error": str(e)}


# ─── Local Testing ──────────────────────────────────────────────────────────
@app.local_entrypoint()
def main():
    print("Testing Whisper STT...")
    print("✅ STT service ready!")
    print("\nTo deploy: modal deploy modal_app/stt.py")

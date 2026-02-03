"""
Modal TTS Service - ElevenLabs
===============================
Best quality AI voices using ElevenLabs API.
"""

import modal

app = modal.App("altiora-tts")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "httpx",
        "fastapi[standard]",
    )
)


@app.function(
    image=image,
    timeout=60,
    scaledown_window=300,
)
@modal.fastapi_endpoint(method="POST")
async def synthesize(request: dict):
    import httpx
    import base64
    import subprocess
    import tempfile
    import os

    text = request.get("text", "")
    language = request.get("language", "en")

    if not text:
        return {"error": "No text provided", "audio_base64": ""}

    # ElevenLabs API key (NEW)
    API_KEY = "sk_2ff8836c7112d906956265b576f8ae9a28b4cfc64bee8767"

    # Voice ID - Rachel (calm, professional female)
    voice_id = "21m00Tcm4TlvDq8ikWAM"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    }
                }
            )

            if response.status_code != 200:
                return {"error": f"ElevenLabs error: {response.status_code}", "audio_base64": ""}

            mp3_bytes = response.content

        # Save MP3
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_bytes)
            mp3_path = f.name

        # Convert to WAV 8kHz mono for Twilio
        wav_path = mp3_path.replace(".mp3", ".wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", mp3_path,
            "-ar", "8000", "-ac", "1", "-f", "wav", wav_path
        ], capture_output=True)

        # Read and encode
        with open(wav_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        # Cleanup
        os.unlink(mp3_path)
        os.unlink(wav_path)

        return {"audio_base64": audio_b64, "sample_rate": 8000}

    except Exception as e:
        return {"error": str(e), "audio_base64": ""}

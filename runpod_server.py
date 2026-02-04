"""
Altiora AI - RunPod Server
===========================
STT (Whisper) + LLM (Llama 3.1) API Server
"""

import asyncio
import base64
import tempfile
import time
import logging

from fastapi import FastAPI
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Altiora AI - RunPod Server")

whisper_model = None


class STTRequest(BaseModel):
    audio: str
    language: str = "en"


class LLMRequest(BaseModel):
    messages: list
    max_tokens: int = 150
    temperature: float = 0.7


@app.on_event("startup")
async def load_models():
    global whisper_model
    logger.info("Loading Whisper model...")
    from faster_whisper import WhisperModel
    whisper_model = WhisperModel("base", device="cuda", compute_type="float16")
    logger.info("✅ Whisper model loaded!")


@app.get("/health")
async def health():
    return {"status": "ok", "stt": "whisper", "llm": "llama3.1"}


@app.post("/stt")
async def speech_to_text(request: STTRequest):
    start = time.time()
    try:
        audio_bytes = base64.b64decode(request.audio)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            f.write(audio_bytes)
            f.flush()
            segments, info = whisper_model.transcribe(
                f.name,
                language=request.language if request.language != "auto" else None,
                beam_size=5,
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments)
        logger.info(f"[STT] {time.time()-start:.2f}s: '{text}'")
        return {"text": text, "language": info.language}
    except Exception as e:
        logger.error(f"[STT] Error: {e}")
        return {"text": "", "error": str(e)}


@app.post("/llm")
async def chat_completion(request: LLMRequest):
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "llama3.1:8b",
                    "messages": request.messages,
                    "stream": False,
                    "options": {
                        "num_predict": request.max_tokens,
                        "temperature": request.temperature,
                    }
                }
            )
            data = response.json()
            text = data.get("message", {}).get("content", "").strip()
        logger.info(f"[LLM] {time.time()-start:.2f}s: '{text[:50]}...'")
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}
    except Exception as e:
        logger.error(f"[LLM] Error: {e}")
        return {"choices": [{"message": {"role": "assistant", "content": "Sorry, error occurred."}}]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

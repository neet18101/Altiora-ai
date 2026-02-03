"""
Altiora AI — Main Server
=========================
FastAPI application handling:
  1. Twilio voice webhook (POST /voice/inbound)
  2. Twilio Media Stream WebSocket (WS /voice/stream)
  3. Outbound call trigger (POST /voice/outbound)
  4. Health check (GET /health)

Usage:
  1. Copy .env.example to .env and fill in your credentials
  2. Run: python main.py
  3. Expose with ngrok: ngrok http 8000
  4. Set your Twilio webhook to: https://your-ngrok-url/voice/inbound
"""

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Connect

from config import config
from twilio_handler import TwilioWebSocketHandler

# ─── Logging Setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("altiora")

# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Altiora AI Voice Server",
    description="AI-powered voice calling platform",
    version="0.1.0",
)

# ─── Twilio Client ───────────────────────────────────────────────────────────
twilio_client = None
if config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": config.PIPELINE_MODE,
        "twilio_configured": bool(config.TWILIO_ACCOUNT_SID),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TWILIO VOICE WEBHOOK — Inbound Calls
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/voice/inbound")
async def voice_inbound(request: Request):
    """
    Twilio calls this webhook when someone dials your Twilio number.
    We respond with TwiML that tells Twilio to open a Media Stream
    (bidirectional WebSocket) to our /voice/stream endpoint.
    """
    logger.info("=== INBOUND CALL RECEIVED ===")

    # Log call details
    form = await request.form()
    caller = form.get("From", "unknown")
    to = form.get("To", "unknown")
    call_sid = form.get("CallSid", "unknown")
    logger.info(f"Call from {caller} to {to} (CallSid: {call_sid})")

    # Build TwiML response
    response = VoiceResponse()

    # Optional: Say something before connecting the stream
    # response.say("Please wait while we connect you.", voice="alice")

    # Connect to our WebSocket for bidirectional audio streaming
    connect = Connect()
    stream = connect.stream(
        url=f"wss://{_get_host(request)}/voice/stream",
        name="altiora-stream",
    )
    # Send audio in both directions
    stream.parameter(name="direction", value="both")
    response.append(connect)

    twiml = str(response)
    logger.info(f"TwiML response:\n{twiml}")

    return Response(content=twiml, media_type="application/xml")


# ═══════════════════════════════════════════════════════════════════════════════
# TWILIO MEDIA STREAM — WebSocket
# ═══════════════════════════════════════════════════════════════════════════════
@app.websocket("/voice/stream")
async def voice_stream(websocket: WebSocket):
    """
    Twilio connects here for bidirectional audio streaming.
    This is where the real-time conversation happens.
    """
    logger.info("=== MEDIA STREAM WEBSOCKET CONNECTING ===")
    handler = TwilioWebSocketHandler()
    await handler.handle(websocket)


# ═══════════════════════════════════════════════════════════════════════════════
# OUTBOUND CALL TRIGGER
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/voice/outbound")
async def voice_outbound(request: Request):
    """
    Trigger an outbound call from the AI to a phone number.

    JSON body:
      { "to": "+1234567890" }

    The AI will call the number and connect via Media Stream.
    """
    if not twilio_client:
        return {"error": "Twilio not configured"}, 500

    data = await request.json()
    to_number = data.get("to")

    if not to_number:
        return {"error": "Missing 'to' phone number"}, 400

    logger.info(f"=== OUTBOUND CALL TO {to_number} ===")

    # Build TwiML for the outbound call
    twiml = f"""
    <Response>
        <Connect>
            <Stream url="wss://{config.PUBLIC_URL.replace('https://', '').replace('http://', '')}/voice/stream" name="altiora-stream">
                <Parameter name="direction" value="both"/>
            </Stream>
        </Connect>
    </Response>
    """

    try:
        call = twilio_client.calls.create(
            to=to_number,
            from_=config.TWILIO_PHONE_NUMBER,
            twiml=twiml.strip(),
        )
        logger.info(f"Outbound call created — CallSid: {call.sid}")
        return {"status": "calling", "call_sid": call.sid, "to": to_number}
    except Exception as e:
        logger.error(f"Failed to create outbound call: {e}")
        return {"error": str(e)}, 500


# ═══════════════════════════════════════════════════════════════════════════════
# CALL STATUS WEBHOOK (optional — Twilio sends call status updates here)
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/voice/status")
async def voice_status(request: Request):
    """Receives call status updates from Twilio."""
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    status = form.get("CallStatus", "unknown")
    duration = form.get("CallDuration", "0")
    logger.info(f"Call status update — {call_sid}: {status} (duration: {duration}s)")
    return {"status": "ok"}


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _get_host(request: Request) -> str:
    """Extract the host from the request, preferring forwarded headers (ngrok)."""
    forwarded = request.headers.get("x-forwarded-host")
    if forwarded:
        return forwarded
    host = request.headers.get("host", "localhost:8000")
    return host


# ═══════════════════════════════════════════════════════════════════════════════
# RUN SERVER
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  ALTIORA AI VOICE SERVER")
    logger.info(f"  Mode: {config.PIPELINE_MODE.upper()}")
    logger.info(f"  Port: {config.SERVER_PORT}")
    logger.info("=" * 60)

    if config.PIPELINE_MODE == "mock":
        logger.info("")
        logger.info("  Running in MOCK mode!")
        logger.info("  Twilio will work, but AI responses are fake.")
        logger.info("  Switch to LIVE mode when RunPod is ready.")
        logger.info("")

    uvicorn.run(
        "main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=True,
        log_level="info",
    )

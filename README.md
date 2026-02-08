# 🚀 Altiora AI - Voice Calling Platform

AI-powered Voice Calling SaaS using Modal serverless GPUs.

## 📁 Project Structure

```
altiora-ai/
├── modal_app/              # Modal serverless functions
│   ├── stt.py              # Speech-to-Text (Whisper)
│   ├── tts.py              # Text-to-Speech (XTTS)
│   └── llm.py              # LLM (Mistral 7B)
│
├── server/                 # FastAPI server
│   ├── main.py             # Main server + Twilio webhooks
│   ├── twilio_handler.py   # WebSocket handler
│   ├── voice_pipeline.py   # AI pipeline orchestration
│   ├── audio_utils.py      # Audio conversion utilities
│   └── config.py           # Configuration
│
├── .env.example            # Environment template
├── deploy_modal.sh         # Modal deployment script
└── README.md
```

## ⚡ Quick Start

### 1. Setup Modal

```bash
# Install Modal
pip install modal

# Login
modal setup
```

### 2. Deploy AI Services to Modal

```bash
# Deploy all services (first time takes 5-10 min)
chmod +x deploy_modal.sh
./deploy_modal.sh

# Or deploy individually
modal deploy modal_app/stt.py
modal deploy modal_app/tts.py
modal deploy modal_app/llm.py
```

### 3. Configure Server

```bash
# Copy env template
cp .env.example .env

# Edit with your values:
# - TWILIO_* credentials
# - MODAL_WORKSPACE=your-workspace
# - PIPELINE_MODE=modal
```

### 4. Run Server

```bash
cd server
pip install -r requirements.txt
python main.py
```

### 5. Expose with ngrok

```bash
ngrok http 8000
```

### 6. Configure Twilio

1. Go to Twilio Console → Phone Numbers
2. Set webhook: `https://your-ngrok-url/voice/inbound`
3. Method: POST

### 7. Make a Test Call! 📞

Call your Twilio number and talk to the AI.

## 🔧 Pipeline Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `mock` | Fake AI responses | Testing Twilio |
| `modal` | Full Modal AI | Production |
| `modal-edge` | Modal + Edge TTS | Faster/cheaper TTS |

Set in `.env`:
```
PIPELINE_MODE=modal
```

## 💰 Modal Pricing (Estimated)

| Service | GPU | Cost/hour | Per Call (~30s) |
|---------|-----|-----------|-----------------|
| STT | T4 | ~$0.60 | ~$0.005 |
| TTS | T4 | ~$0.60 | ~$0.005 |
| LLM | A10G | ~$1.10 | ~$0.01 |

**Total: ~$0.02 per 30-second call**

## 🚀 Next Steps

- [ ] Add database (PostgreSQL)
- [ ] User authentication
- [ ] Business dashboard
- [ ] Stripe billing
- [ ] Call recordings storage
- [ ] Analytics

## 📞 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/voice/inbound` | POST | Twilio webhook |
| `/voice/stream` | WS | Media stream |
| `/voice/outbound` | POST | Make outbound call |

## 🤝 Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Caller    │────▶│   Twilio    │────▶│  FastAPI Server │
└─────────────┘     └─────────────┘     └────────┬────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                    Modal   │ (Serverless GPU)           │
                    │  ┌─────────┐    ┌─────────┴─────────┐    ┌──────────┐  │
                    │  │   STT   │───▶│        LLM        │───▶│   TTS    │  │
                    │  │ Whisper │    │  Mistral 7B       │    │  XTTS    │  │
                    │  └─────────┘    └───────────────────┘    └──────────┘  │
                    └─────────────────────────────────────────────────────────┘
```



=========================================
# 📋 Altiora AI - Full Context (Kal Paste Karna)

---

## 🎯 Project: Altiora AI Voice Calling Platform

**Kya hai:** AI Voice Agent jo real phone calls handle kare (Twilio + AI)

**Flow:**
```
Phone Call → Twilio → Server → STT (Whisper) → LLM (Mistral) → TTS → Audio Response
```

---

## ✅ Aaj Kya Complete Hua:

### 1. Modal Deployed (Serverless GPU)
- **STT:** `https://neet18101--altiora-stt-transcribe-audio.modal.run` ✅
- **LLM:** `https://neet18101--altiora-llm-chat.modal.run` ✅
- Workspace: `neet18101`

### 2. Twilio Working
- Number: `+12722036919`
- Outbound calls ✅
- WebSocket Media Stream ✅

### 3. Server Code Ready
Location: `E:\2026\altiora-modal\server\`
- main.py ✅
- twilio_handler.py ✅
- audio_utils.py ✅
- config.py ✅
- voice_pipeline.py ⚠️ (TTS fix needed)

---

## ❌ Pending: TTS Fix

Tried & Failed:
- XTTS → License prompt issue
- Edge TTS → IP blocked
- ElevenLabs → Free tier blocked

**Solution:** Use **gTTS** (Google TTS - FREE)

---

## 🚀 Kal Karna Hai:

### Step 1: gTTS Install
```powershell
cd E:\2026\altiora-modal
.\venv\Scripts\Activate
pip install gTTS
```

### Step 2: ffmpeg Install (if needed)
```powershell
winget install ffmpeg
```

### Step 3: Replace `server/voice_pipeline.py` with gTTS version

### Step 4: Test Call
```powershell
cd server
python main.py

# New terminal:
curl -X POST "http://localhost:8000/voice/outbound" -H "Content-Type: application/json" -d "{\"to\": \"+918887061958\"}"
```

---

## 🔑 Credentials:
- See `.env` file for credentials
- Modal Workspace: `neet18101`

---

**Ye pura message kal naye conversation mein paste kar dena, main samajh jaunga!** 👍




supbase key 
WcV24vTJXiuZ0oVQ



Tumhare FastAPI voice server mein ye 4 changes karne hain:

.env mein SAAS_BACKEND_URL=http://localhost:5000 add karo
Jab inbound call aaye (/voice/inbound) — Node.js backend ko call-started webhook bhejo (caller, to_number, call_sid, direction)
Jab call khatam ho (/voice/status) — Node.js backend ko call-ended webhook bhejo (call_sid, duration)
Jab har message process ho (tumhare voice_pipeline.py ya twilio_handler.py mein jahan STT → LLM → TTS hota hai) — Node.js backend ko transcript webhook bhejo (call_id, speaker, message)

Bas itna hi. Tumhara FastAPI server wahi kaam karega jo kar raha hai — bus har event pe ek HTTP POST extra marega Node.js backend ko, taaki SaaS dashboard mein call logs aur transcripts dikhen.

==============================================================================================================


10:14 PM
Tumhare Node.js backend mein 3 webhook APIs hain jo FastAPI call karega:

1. /api/webhooks/call-started (POST)

Kab: Jab call shuru ho (inbound ya outbound)
Body bhejo:
json
{
  "business_id": "uuid",
  "agent_id": "uuid",
  "direction": "inbound",
  "from_number": "+919999999999",
  "to_number": "+12722036919",
  "twilio_call_sid": "CAxxxxxxxx"
}
Response milega: { "call_id": "uuid" } — ye save karo, baaki webhooks mein chahiye
2. /api/webhooks/call-ended (POST)

Kab: Jab call khatam ho
Body bhejo:
json
{
  "call_id": "uuid",
  "duration_secs": 45,
  "outcome": "completed",
  "sentiment": "positive",
  "summary": "Customer asked about pricing"
}
3. /api/webhooks/transcript (POST)

Kab: Har message ke baad (caller bole ya AI bole)
Body bhejo:
json
{
  "call_id": "uuid",
  "speaker": "caller",
  "message": "Hello, I need help with my order",
  "timestamp_secs": 5.2,
  "stt_duration_ms": 800,
  "llm_duration_ms": 500,
  "tts_duration_ms": 900
}
```
`speaker` value: `"caller"` ya `"agent"`

---

**Flow:**
```
Call shuru → /call-started (call_id milega)
    ↓
Har message → /transcript (call_id use karo)
    ↓
Call khatam → /call-ended (call_id use karo)
Bas ye 3 API calls FastAPI se maaro — saara data dashboard mein aa jayega. Bolo toh FastAPI side ka code bhi de doon?
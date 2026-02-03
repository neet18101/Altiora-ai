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
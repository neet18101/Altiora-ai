#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# ALTIORA AI - Modal Deployment Script
# ═══════════════════════════════════════════════════════════════════════════════
# 
# Usage: ./deploy_modal.sh [component]
# 
# Components:
#   all  - Deploy all services (default)
#   stt  - Deploy only STT (Whisper)
#   tts  - Deploy only TTS (XTTS)
#   llm  - Deploy only LLM (Mistral)
#
# Examples:
#   ./deploy_modal.sh        # Deploy all
#   ./deploy_modal.sh stt    # Deploy only STT
# ═══════════════════════════════════════════════════════════════════════════════

set -e

COMPONENT=${1:-all}

echo "═══════════════════════════════════════════════════════════════════════"
echo "  ALTIORA AI - Modal Deployment"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

# Check if Modal CLI is installed
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI not found. Install with: pip install modal"
    exit 1
fi

# Check if logged in
if ! modal profile list &> /dev/null; then
    echo "❌ Not logged in to Modal. Run: modal setup"
    exit 1
fi

deploy_stt() {
    echo "🎤 Deploying STT (Whisper)..."
    modal deploy modal_app/stt.py
    echo "✅ STT deployed!"
    echo ""
}

deploy_tts() {
    echo "🔊 Deploying TTS (XTTS)..."
    modal deploy modal_app/tts.py
    echo "✅ TTS deployed!"
    echo ""
}

deploy_llm() {
    echo "🧠 Deploying LLM (Mistral)..."
    echo "   ⚠️  First deployment may take 5-10 minutes to download model..."
    modal deploy modal_app/llm.py
    echo "✅ LLM deployed!"
    echo ""
}

case $COMPONENT in
    all)
        deploy_stt
        deploy_tts
        deploy_llm
        ;;
    stt)
        deploy_stt
        ;;
    tts)
        deploy_tts
        ;;
    llm)
        deploy_llm
        ;;
    *)
        echo "❌ Unknown component: $COMPONENT"
        echo "   Valid options: all, stt, tts, llm"
        exit 1
        ;;
esac

echo "═══════════════════════════════════════════════════════════════════════"
echo "  ✅ Deployment Complete!"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "Your endpoints:"
WORKSPACE=$(modal profile current 2>/dev/null | grep -oP '(?<=workspace: )\S+' || echo "your-workspace")
echo "  STT: https://${WORKSPACE}--altiora-stt-transcribe.modal.run"
echo "  TTS: https://${WORKSPACE}--altiora-tts-synthesize.modal.run"
echo "  LLM: https://${WORKSPACE}--altiora-llm-chat.modal.run"
echo ""
echo "Next steps:"
echo "  1. Update .env with PIPELINE_MODE=modal"
echo "  2. Start your server: python main.py"
echo "  3. Start ngrok: ngrok http 8000"
echo "  4. Make a test call!"
echo ""

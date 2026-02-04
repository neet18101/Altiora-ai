from elevenlabs import ElevenLabs

client = ElevenLabs(
    api_key="sk_6c0c668c900d867f549189796e9340c02859847c8212906e")

audio = client.text_to_speech.convert(
    text="Hello, this is a test.",
    voice_id="21m00Tcm4TlvDq8ikWAM",
    model_id="eleven_flash_v2_5",
    output_format="mp3_44100_128",
)

# Save audio
with open("test.mp3", "wb") as f:
    for chunk in audio:
        f.write(chunk)

print("✅ Audio saved to test.mp3")

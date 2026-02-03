"""
Modal LLM Service - Mistral 7B
===============================
Serverless LLM using vLLM on Modal GPU.

Usage:
    modal deploy modal_app/llm.py
"""

import modal

# ─── Modal App Setup ────────────────────────────────────────────────────────
app = modal.App("altiora-llm")

# Docker image with vLLM
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.6.4.post1",
        "transformers",
        "accelerate",
        "fastapi[standard]",
    )
)

# Cache for LLM model weights
model_cache = modal.Volume.from_name("llm-cache", create_if_missing=True)

# Model to use
MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"


# ─── LLM Class ──────────────────────────────────────────────────────────────
@app.cls(
    image=image,
    gpu="A10G",
    timeout=120,
    scaledown_window=300,
    volumes={"/root/.cache/huggingface": model_cache},
)
class MistralLLM:
    @modal.enter()
    def load_model(self):
        """Load LLM when container starts."""
        from vllm import LLM, SamplingParams

        self.llm = LLM(
            model=MODEL_NAME,
            dtype="float16",
            max_model_len=4096,
            gpu_memory_utilization=0.9,
        )

        print(f"✅ {MODEL_NAME} loaded!")

    @modal.method()
    def generate(self, messages: list, max_tokens: int = 150, temperature: float = 0.7) -> str:
        """Generate a response given conversation history."""
        from vllm import SamplingParams

        prompt = self._format_prompt(messages)

        params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            stop=["</s>", "[INST]", "[/INST]"],
        )

        outputs = self.llm.generate([prompt], params)
        response = outputs[0].outputs[0].text.strip()

        return response

    def _format_prompt(self, messages: list) -> str:
        """Format messages into Mistral prompt format."""
        prompt_parts = []
        system_msg = ""

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_msg = content
            elif role == "user":
                if system_msg and not prompt_parts:
                    prompt_parts.append(
                        f"<s>[INST] {system_msg}\n\n{content} [/INST]")
                    system_msg = ""
                else:
                    prompt_parts.append(f"<s>[INST] {content} [/INST]")
            elif role == "assistant":
                prompt_parts.append(f" {content}</s>")

        return "".join(prompt_parts)


# ─── Web Endpoint ───────────────────────────────────────────────────────────
@app.function(
    image=image,
    gpu="A10G",
    timeout=120,
    scaledown_window=300,
    volumes={"/root/.cache/huggingface": model_cache},
)
@modal.fastapi_endpoint(method="POST")
async def chat(request: dict):
    """
    HTTP endpoint for chat completions.

    POST /chat
    Body: {
        "messages": [
            {"role": "system", "content": "You are helpful..."},
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 150,
        "temperature": 0.7
    }
    """
    from vllm import LLM, SamplingParams

    messages = request.get("messages", [])
    max_tokens = request.get("max_tokens", 150)
    temperature = request.get("temperature", 0.7)

    if not messages:
        return {"error": "No messages provided", "choices": []}

    # Load model
    llm = LLM(
        model=MODEL_NAME,
        dtype="float16",
        max_model_len=4096,
        gpu_memory_utilization=0.9,
    )

    # Format prompt
    prompt_parts = []
    system_msg = ""

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            system_msg = content
        elif role == "user":
            if system_msg and not prompt_parts:
                prompt_parts.append(
                    f"<s>[INST] {system_msg}\n\n{content} [/INST]")
                system_msg = ""
            else:
                prompt_parts.append(f"<s>[INST] {content} [/INST]")
        elif role == "assistant":
            prompt_parts.append(f" {content}</s>")

    prompt = "".join(prompt_parts)

    params = SamplingParams(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        stop=["</s>", "[INST]"],
    )

    outputs = llm.generate([prompt], params)
    response = outputs[0].outputs[0].text.strip()

    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": response,
                }
            }
        ]
    }


# ─── Local Testing ──────────────────────────────────────────────────────────
@app.local_entrypoint()
def main():
    print(f"Testing LLM: {MODEL_NAME}")
    print("✅ LLM service ready!")
    print("\nTo deploy: modal deploy modal_app/llm.py")
    print("\n⚠️ Note: First deploy takes 5-10 minutes to download model.")

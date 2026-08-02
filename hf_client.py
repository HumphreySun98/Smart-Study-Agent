# hf_client.py
# Anthropic-shaped wrappers around any OpenAI-compatible endpoint:
# HF Inference router, Ollama, LM Studio, vLLM, DeepSeek, OpenAI, ...
# Haofei Sun - CSE 5360

import os


DEFAULT_MODEL = "moonshotai/Kimi-K2-Instruct-0905"
HF_BASE_URL = "https://router.huggingface.co/v1"
OLLAMA_BASE_URL = "http://localhost:11434/v1"


class _TextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str):
        self.content = [_TextBlock(text)]


class OpenAICompatAdapter:
    """Drop-in replacement for anthropic.Anthropic() backed by any
    OpenAI-compatible /chat/completions endpoint."""

    class _Messages:
        def __init__(self, parent):
            self.parent = parent

        def create(self, model, max_tokens, messages, system="",
                   thinking=None, **kwargs):
            import time
            openai_messages = []
            if system:
                # tighter JSON contract — open-weight models drift more than Claude
                system = system + (
                    "\n\nIMPORTANT: Respond with ONLY a valid JSON object/array. "
                    "No prose, no markdown fences, no commentary before or after."
                )
                openai_messages.append({"role": "system", "content": system})
            for m in messages:
                openai_messages.append({"role": m["role"], "content": m["content"]})

            # retry on empty responses; lower temperature each try
            last_text = ""
            for attempt in range(3):
                temp = [0.3, 0.1, 0.0][attempt]
                try:
                    completion = self.parent.client.chat.completions.create(
                        model=self.parent.model,
                        messages=openai_messages,
                        max_tokens=max(max_tokens, 1500),
                        temperature=temp,
                    )
                    text = completion.choices[0].message.content or ""
                    if text.strip():
                        return _Response(text)
                    last_text = text
                except Exception:
                    if attempt == 2:
                        raise
                time.sleep(0.6 * (attempt + 1))

            return _Response(last_text)

    def __init__(self, base_url: str, api_key: str = None,
                 model: str = DEFAULT_MODEL):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("This backend requires `pip install openai`")

        self.client = OpenAI(
            base_url=base_url,
            # Ollama/LM Studio ignore the key but the SDK requires one
            api_key=api_key or "not-needed",
        )
        self.model = model
        self.messages = self._Messages(self)


class HFAnthropicAdapter(OpenAICompatAdapter):
    """HF Inference router preset (kept for backward compatibility)."""

    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL):
        super().__init__(
            base_url=HF_BASE_URL,
            api_key=api_key or os.environ.get("HF_TOKEN"),
            model=model,
        )


def from_env():
    """Build an adapter from SMARTSTUDY_LLM_* env vars, or None if unset.

    SMARTSTUDY_LLM_BASE_URL  — any OpenAI-compatible endpoint
                               (shortcut: "ollama" → http://localhost:11434/v1)
    SMARTSTUDY_LLM_MODEL     — model name at that endpoint
    SMARTSTUDY_LLM_API_KEY   — optional; local servers don't need one
    """
    base_url = os.environ.get("SMARTSTUDY_LLM_BASE_URL")
    if not base_url:
        return None
    if base_url.strip().lower() == "ollama":
        base_url = OLLAMA_BASE_URL
    model = os.environ.get("SMARTSTUDY_LLM_MODEL", "llama3.1")
    return OpenAICompatAdapter(
        base_url=base_url,
        api_key=os.environ.get("SMARTSTUDY_LLM_API_KEY"),
        model=model,
    )

# hf_client.py
# Hugging Face Inference adapter that mimics the Anthropic SDK interface
# Lets us run the agent for free using HF Inference Providers
# Uses an OpenAI-compatible chat completion endpoint
# Haofei Sun - CSE 5360

import os


# default model - Kimi K2 is one of the best free options on HF
DEFAULT_MODEL = "moonshotai/Kimi-K2-Instruct-0905"


class _TextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text: str):
        self.content = [_TextBlock(text)]


class HFAnthropicAdapter:
    """
    Drop-in replacement for anthropic.Anthropic() that calls
    HF Inference Providers via the OpenAI-compatible router.
    The .messages.create() signature matches Anthropic exactly so
    the rest of the agent code doesn't need to change.
    """

    class _Messages:
        def __init__(self, parent):
            self.parent = parent

        def create(self, model, max_tokens, messages, system="",
                   thinking=None, **kwargs):
            # convert anthropic messages format to openai format
            openai_messages = []
            if system:
                openai_messages.append({"role": "system", "content": system})
            for m in messages:
                openai_messages.append({"role": m["role"], "content": m["content"]})

            completion = self.parent.client.chat.completions.create(
                model=self.parent.model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )

            text = completion.choices[0].message.content or ""
            return _Response(text)

    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("HF backend requires `pip install openai`")

        self.client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=api_key or os.environ.get("HF_TOKEN"),
        )
        self.model = model
        self.messages = self._Messages(self)

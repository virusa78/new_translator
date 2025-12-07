# llm_client.py
import time
from typing import Tuple, Any, Dict

import requests  # type: ignore

from errors import ExceedContextSizeError


class BaseLLMClient:
    def translate(self, system_prompt: str, user_prompt: str) -> Tuple[str, float]:
        raise NotImplementedError


class LlamaCppClient(BaseLLMClient):
    """
    llama.cpp server (llama-server) with OpenAI-compatible /v1/chat/completions.
    """

    def __init__(self, url: str, model: str, timeout: int = 600):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def translate(self, system_prompt: str, user_prompt: str) -> Tuple[str, float]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }

        t0 = time.time()
        resp = requests.post(self.url, json=payload, timeout=self.timeout)  # type: ignore
        t1 = time.time()

        txt = resp.text

        # Специальная обработка нехватки контекста
        if resp.status_code == 400 and (
            "exceed_context_size_error" in txt
            or "exceeds the available context size" in txt
        ):
            raise ExceedContextSizeError(
                f"llama.cpp context exceeded: {txt[:400]}"
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"llama.cpp error HTTP {resp.status_code}: {txt[:400]}"
            )

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(
                f"Unexpected llama.cpp response format: {e}, body={data}"
            )

        return content, t1 - t0


class OllamaClient(BaseLLMClient):
    """
    Ollama /api/generate client.

    Default URL: http://localhost:11434/api/generate
    """

    def __init__(
        self,
        url: str,
        model: str,
        timeout: int = 600,
        options: Dict[str, Any] | None = None,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.options = options or {}

    def translate(self, system_prompt: str, user_prompt: str) -> Tuple[str, float]:
        prompt = f"System:\n{system_prompt}\n\nUser:\n{user_prompt}\n\nAssistant:"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                "temperature": 0.0,
                **self.options,
            },
            "stream": False,
        }

        t0 = time.time()
        resp = requests.post(self.url, json=payload, timeout=self.timeout)  # type: ignore
        t1 = time.time()

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama error HTTP {resp.status_code}: {resp.text[:400]}"
            )

        data = resp.json()
        try:
            content = data.get("response", "")
        except Exception as e:
            raise RuntimeError(
                f"Unexpected Ollama response format: {e}, body={data}"
            )

        return content, t1 - t0

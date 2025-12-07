# core/llm_client.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Tuple, Dict, Any

import requests  # type: ignore

from .errors import ExceedContextSizeError


@dataclass
class BaseLLMClient:
    """
    Базовый интерфейс для всех LLM-клиентов.
    Все реализации обязаны иметь метод:
        translate(system_prompt, user_prompt) -> (text, dt_seconds)
    """

    def translate(self, system_prompt: str, user_prompt: str) -> Tuple[str, float]:
        raise NotImplementedError


@dataclass
class LlamaCppClient(BaseLLMClient):
    """
    Клиент для llama.cpp (llama-server) с OpenAI-совместимым API:
    POST /v1/chat/completions
    """

    url: str
    model: str
    timeout: int = 600

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
        resp = requests.post(self.url, json=payload, timeout=self.timeout)
        t1 = time.time()

        text_body = resp.text

        # Специальная обработка переполнения контекста
        if resp.status_code == 400 and (
            "exceed_context_size_error" in text_body
            or "exceeds the available context size" in text_body
        ):
            raise ExceedContextSizeError(
                f"llama.cpp context exceeded: {text_body[:400]}"
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"llama.cpp error HTTP {resp.status_code}: {text_body[:400]}"
            )

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(
                f"Unexpected llama.cpp response format: {e}, body={data}"
            )

        return content, t1 - t0


@dataclass
class OllamaClient(BaseLLMClient):
    """
    Клиент для Ollama /api/generate.

    По контракту тоже предоставляет:
        translate(system_prompt, user_prompt) -> (text, dt_seconds)
    """

    url: str
    model: str
    timeout: int = 600
    options: Dict[str, Any] | None = None

    def translate(self, system_prompt: str, user_prompt: str) -> Tuple[str, float]:
        prompt = f"System:\n{system_prompt}\n\nUser:\n{user_prompt}\n\nAssistant:"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                "temperature": 0.0,
                **(self.options or {}),
            },
            "stream": False,
        }

        t0 = time.time()
        resp = requests.post(self.url, json=payload, timeout=self.timeout)
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

# core/llm_client.py
from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Tuple, Dict, Any

import requests  # type: ignore

from .errors import ExceedContextSizeError

logger = logging.getLogger("translator.llm")


@dataclass
class BaseLLMClient:
    def translate(self, system_prompt: str, user_prompt: str) -> Tuple[str, float]:
        raise NotImplementedError


@dataclass
class LlamaCppClient(BaseLLMClient):
    url: str
    model: str
    timeout: int = 60  # меньше, чтобы не висело на минутами

    def translate(self, system_prompt: str, user_prompt: str) -> Tuple[str, float]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }

        logger.info(
            f"[LLM] llama.cpp call → {self.url} model={self.model}, "
            f"user_prompt_len={len(user_prompt)}"
        )

        t0 = time.time()
        resp = requests.post(self.url, json=payload, timeout=self.timeout)
        t1 = time.time()

        dt = t1 - t0
        text_body = resp.text

        logger.info(f"[LLM] llama.cpp response HTTP {resp.status_code} in {dt:.2f}s")

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

        return content, dt


@dataclass
class OllamaClient(BaseLLMClient):
    url: str
    model: str
    timeout: int = 60
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

        logger.info(
            f"[LLM] Ollama call → {self.url} model={self.model}, "
            f"user_prompt_len={len(user_prompt)}"
        )

        t0 = time.time()
        resp = requests.post(self.url, json=payload, timeout=self.timeout)
        t1 = time.time()

        dt = t1 - t0
        logger.info(f"[LLM] Ollama response HTTP {resp.status_code} in {dt:.2f}s")

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

        return content, dt

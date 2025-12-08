# core/string_translator.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import logging

from .llm_client import BaseLLMClient
from .stats import Stats

logger = logging.getLogger("translator.strings")


@dataclass
class StringTranslator:
    """
    Переводит *строки* через LLM, с кэшем и строгим промтом.

    Единый внешний интерфейс:
        translate(text: str) -> str   # для целого файла .txt/.md
    Плюс:
        translate_string(s: str) -> str  # для Java-комментариев и строковых литералов
    """

    client: BaseLLMClient
    source_lang: str
    target_lang: str
    stats: Stats
    glossary_path: Path

    def __post_init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self._system_prompt = self._build_system_prompt()

        self.glossary_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.glossary_path.exists():
            self.glossary_path.write_text(
                "# original\ttranslation\n", encoding="utf-8"
            )

    # -------- PROMPT --------

    def _build_system_prompt(self) -> str:
        # максимально сухой, без лишних токенов
        return (
            f"ROLE:\n"
            f"You are a strict technical translator for source code.\n"
            f"Task: Translate text from {self.source_lang} to {self.target_lang}.\n\n"
            "RULES:\n"
            "1. Answer ONLY with the translation – NOTHING ELSE.\n"
            "2. NO explanations, NO comments, NO repetition of source.\n"
            "3. PRESERVE all backslashes and escape sequences exactly.\n"
            "4. PRESERVE formatting, line breaks and indentation.\n"
            "5. Do NOT change code syntax, only natural-language text.\n"
        )

    # -------- LLM CALL --------

    def _call_llm(self, text: str) -> str:
        user_prompt = f"Text to translate:\n{text}\n\nTranslation:"
        translated, dt = self.client.translate(self._system_prompt, user_prompt)

        self.stats.llm_time_seconds += dt
        self.stats.total_words += len(translated.split())

        t = translated.strip()
        # Часто модели зачем-то оборачивают в кавычки — снимем
        if (t.startswith('"') and t.endswith('"')) or (
            t.startswith("'") and t.endswith("'")
        ):
            t = t[1:-1].strip()
        return t

    def _log_glossary_pair(self, src: str, dst: str) -> None:
        try:
            with self.glossary_path.open("a", encoding="utf-8") as f:
                f.write(
                    src.replace("\n", "\\n")
                    + "\t"
                    + dst.replace("\n", "\\n")
                    + "\n"
                )
        except Exception:
            # глоссарий не должен ломать пайплайн
            pass

    # -------- PUBLIC API --------

    def translate_string(self, s: str) -> str:
        """Перевод одной строки (используется JavaTranslator)."""
        if not s:
            return s
        if s in self._cache:
            return self._cache[s]

        t = self._call_llm(s)
        self._cache[s] = t
        self._log_glossary_pair(s, t)
        return t

    def translate(self, text: str) -> str:
        """
        Унифицированный метод для целикового текстового файла (.txt / .md).

        MVP: переводим всё одним куском через тот же строгий промт.
        """
        return self.translate_string(text)

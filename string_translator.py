# string_translator.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from llm_client import BaseLLMClient
from stats import Stats
from prompts import build_code_system_prompt, build_user_prompt_for_string


def is_i18n_key_like(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    if " " in s:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return all(ch in allowed for ch in s)


def looks_like_path_or_technical(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    if ("\\" in s or "/" in s) and " " not in s:
        return True
    return False


def is_human_visible_string(s: str) -> bool:
    """
    Грубая эвристика: стоит ли вообще отправлять строку на перевод.
    """
    s_stripped = s.strip()
    if not s_stripped:
        return False
    if is_i18n_key_like(s_stripped):
        return False
    if looks_like_path_or_technical(s_stripped):
        return False

    # Если есть пробелы или типичная пунктуация — почти точно текст для человека
    if " " in s_stripped:
        return True
    if any(ch in s_stripped for ch in [".", ",", "!", "?", ":"]):
        return True

    # Одно слово типа "Ошибка" / "Error" — тоже человек
    return True


# --- маскировка плейсхолдеров --------------------------------------------

# %s, %d, %1$s, %02d, etc.
_FMT_RE = r"%(\d+\$)?[0-9.\-+]*[sdfx]"
# {0}, {1}
_BRACE_INDEX_RE = r"\{[0-9]+\}"
# ${varName}
_DOLLAR_VAR_RE = r"\$\{[^}]+\}"
# escapes: \n, \t, \r, \"
_ESCAPES_RE = r"\\[ntr\"']"

_PLACEHOLDER_PATTERN = re.compile(
    "|".join(
        [
            _FMT_RE,
            _BRACE_INDEX_RE,
            _DOLLAR_VAR_RE,
            _ESCAPES_RE,
        ]
    )
)


def mask_placeholders(text: str) -> tuple[str, Dict[str, str]]:
    """
    Заменяем плейсхолдеры на __PH_i__, чтобы LLM их не ломала.
    """
    mapping: Dict[str, str] = {}
    counter = 0

    def repl(m: re.Match) -> str:
        nonlocal counter
        original = m.group(0)
        key = f"__PH_{counter}__"
        mapping[key] = original
        counter += 1
        return key

    masked = _PLACEHOLDER_PATTERN.sub(repl, text)
    return masked, mapping


def unmask_placeholders(text: str, mapping: Dict[str, str]) -> str:
    for key, original in mapping.items():
        text = text.replace(key, original)
    return text


@dataclass
class StringTranslator:
    client: BaseLLMClient
    source_lang: str
    target_lang: str
    stats: Stats
    glossary_path: Path

    def __post_init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self._system_prompt = build_code_system_prompt(
            self.source_lang, self.target_lang
        )
        self.glossary_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.glossary_path.exists():
            self.glossary_path.write_text(
                "# original\ttranslation\n", encoding="utf-8"
            )

    # --- glossary log -----------------------------------------------------

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
            # Не хотим падать из-за проблем с глоссарием
            pass

    # --- основной метод ---------------------------------------------------

    def translate_string(self, s: str) -> str:
        """
        Перевод одной строки с кэшированием, маскировкой плейсхолдеров и
        базовой статистикой.
        """
        s_key = s
        if s_key in self._cache:
            return self._cache[s_key]

        if not is_human_visible_string(s):
            self._cache[s_key] = s
            return s

        masked, mapping = mask_placeholders(s)

        user_prompt = build_user_prompt_for_string(
            masked, self.source_lang, self.target_lang
        )

        translated, dt = self.client.translate(self._system_prompt, user_prompt)

        self.stats.llm_time_seconds += dt
        self.stats.total_input_chars += len(s)
        self.stats.total_output_chars += len(translated)
        self.stats.total_words += len(translated.split())

        t = translated.strip()
        # На всякий случай — иногда модель оборачивает в кавычки
        if (t.startswith('"') and t.endswith('"')) or (
            t.startswith("'") and t.endswith("'")
        ):
            t = t[1:-1].strip()

        t = unmask_placeholders(t, mapping)

        self._cache[s_key] = t
        self._log_glossary_pair(s, t)
        return t

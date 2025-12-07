# java_translator.py
from __future__ import annotations

from pathlib import Path
import logging

from stats import Stats
from string_translator import StringTranslator


class JavaTranslator:
    """
    Переводит только строковые литералы и комментарии в .java файлах.
    Остальной код (сигнатуры, логика) остаётся байт-в-байт.
    """

    def __init__(
        self,
        string_translator: StringTranslator,
        stats: Stats,
        logger: logging.Logger,
    ):
        self.string_translator = string_translator
        self.stats = stats
        self.logger = logger

    # ------------------------------------------------------------------ #
    # Внутренний парсер: идём по тексту и обрабатываем "атомы":
    #   - // line comment
    #   - /* block comment */
    #   - "string literal"
    # Остальное копируем как есть.
    # ------------------------------------------------------------------ #

    def translate_text(self, text: str) -> str:
        out: list[str] = []
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]

            # line comment //
            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                out.append("//")
                i += 2
                # до конца строки или файла
                start = i
                while i < n and text[i] not in "\r\n":
                    i += 1
                comment = text[start:i]
                translated = self.string_translator.translate_string(comment)
                out.append(translated)
                # перенос строки копируем как есть
                if i < n:
                    out.append(text[i])
                    i += 1
                continue

            # block comment /* ... */
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                out.append("/*")
                i += 2
                start = i
                end = text.find("*/", i)
                if end == -1:
                    # нет закрывающего */ — считаем до конца файла
                    comment = text[start:]
                    translated = self.string_translator.translate_string(comment)
                    out.append(translated)
                    break
                else:
                    comment = text[start:end]
                    translated = self.string_translator.translate_string(comment)
                    out.append(translated)
                    out.append("*/")
                    i = end + 2
                continue

            # string literal "..."
            if ch == '"':
                out.append('"')
                i += 1
                start = i
                escaped = False
                while i < n:
                    c = text[i]
                    if escaped:
                        escaped = False
                        i += 1
                        continue
                    if c == "\\":
                        escaped = True
                        i += 1
                        continue
                    if c == '"':
                        break
                    i += 1

                # inner text без кавычек
                inner = text[start:i]
                translated_inner = self.string_translator.translate_string(inner)
                out.append(translated_inner)

                # закрывающая кавычка, если есть
                if i < n and text[i] == '"':
                    out.append('"')
                    i += 1
                continue

            # char literal 'c' или '\n' — не трогаем, просто пропускаем
            if ch == "'" and i + 1 < n:
                out.append("'")
                i += 1
                start = i
                escaped = False
                while i < n:
                    c = text[i]
                    if escaped:
                        escaped = False
                        i += 1
                        continue
                    if c == "\\":
                        escaped = True
                        i += 1
                        continue
                    if c == "'":
                        break
                    i += 1
                # содержимое просто копируем
                out.append(text[start:i])
                if i < n and text[i] == "'":
                    out.append("'")
                    i += 1
                continue

            # по умолчанию — копируем символ
            out.append(ch)
            i += 1

        return "".join(out)

    # ------------------------------------------------------------------ #

    def translate_file(self, src: Path, dst: Path) -> None:
        try:
            text = src.read_text(encoding="utf-8")
        except Exception as e:
            self.stats.error_files += 1
            msg = f"[ERROR] Cannot read Java file {src}: {e}"
            self.logger.error(msg, exc_info=True)
            self.stats.errors.append(msg)
            return

        translated = self.translate_text(text)

        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            dst.write_text(translated, encoding="utf-8")
        except Exception as e:
            self.stats.error_files += 1
            msg = f"[ERROR] Cannot write Java file {dst}: {e}"
            self.logger.error(msg, exc_info=True)
            self.stats.errors.append(msg)
            return

        self.stats.translated_files += 1
        self.stats.total_files += 1

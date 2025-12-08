# java_translator.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, List

from core.string_translator import StringTranslator


def _is_escaped(source: str, idx: int) -> bool:
    """
    Проверяет, экранирован ли символ source[idx] обратными слешами слева.
    Пример:  a = "foo\\\"bar"
                        ^
    Для этой кавычки вернём True.
    """
    backslashes = 0
    j = idx - 1
    while j >= 0 and source[j] == "\\":
        backslashes += 1
        j -= 1
    return (backslashes % 2) == 1


@dataclass
class JavaTranslator:
    """
    Переводчик Java-файлов уровня текста:
    - переводит строковые литералы "..."
    - переводит комментарии // ... и /* ... */
    - не трогает char-литералы и сам код
    IO не делает, работает только text -> text.
    """

    string_translator: StringTranslator
    logger: logging.Logger

    def translate(self, text: str, file_label: Optional[str] = None) -> str:
        """
        Основной метод перевода Java-исходника.

        :param text: полный текст Java-файла
        :param file_label: относительный путь для логов (опционально)
        :return: текст с переведёнными строками и комментариями
        """
        label = file_label or "<java>"
        self.logger.info(
            f"[JAVA] Translating {label} (len={len(text)} chars)"
        )

        NORMAL = 0
        STRING = 1
        CHAR = 2
        LINE_COMMENT = 3
        BLOCK_COMMENT = 4

        mode = NORMAL
        result: List[str] = []
        buf: List[str] = []  # для содержимого строк/комментов

        i = 0
        n = len(text)

        def translate_buffer(kind: str) -> str:
            """
            kind: 'string' или 'comment'
            Через StringTranslator переводим только содержимое,
            а кавычки/делимтеры остаются снаружи.
            """
            nonlocal buf
            inner = "".join(buf)
            buf = []
            if not inner:
                return ""

            try:
                translated = self.string_translator.translate_string(inner)
                return translated
            except Exception as e:
                self.logger.error(
                    f"[JAVA] Error translating {kind} in {label}: {e}"
                )
                # В случае ошибки безопаснее оставить исходное содержимое
                return inner

        while i < n:
            ch = text[i]

            # ---------------- NORMAL CODE ----------------
            if mode == NORMAL:
                # начало строкового литерала
                if ch == '"':
                    mode = STRING
                    buf = []
                    result.append('"')
                    i += 1
                    continue

                # начало char-литерала
                if ch == "'":
                    mode = CHAR
                    result.append("'")
                    i += 1
                    continue

                # начало // комментария
                if ch == "/" and i + 1 < n and text[i + 1] == "/":
                    mode = LINE_COMMENT
                    buf = []
                    result.append("//")
                    i += 2
                    continue

                # начало /* или /** комментария
                if ch == "/" and i + 1 < n and text[i + 1] == "*":
                    mode = BLOCK_COMMENT
                    buf = []
                    result.append("/*")
                    i += 2
                    # Javadoc /** – копируем дополнительную *
                    if i < n and text[i] == "*":
                        result.append("*")
                        i += 1
                    continue

                # обычный код
                result.append(ch)
                i += 1
                continue

            # ---------------- STRING LITERAL ----------------
            if mode == STRING:
                if ch == '"' and not _is_escaped(text, i):
                    # закрытие строки
                    translated_inner = translate_buffer("string")
                    result.append(translated_inner)
                    result.append('"')
                    mode = NORMAL
                    i += 1
                    continue
                else:
                    buf.append(ch)
                    i += 1
                    continue

            # ---------------- CHAR LITERAL ----------------
            if mode == CHAR:
                # char-литералы не переводим — просто копируем до закрывающей '
                result.append(ch)
                # закрытие char-литерала неэкранированной кавычкой
                if ch == "'" and not _is_escaped(text, i):
                    mode = NORMAL
                i += 1
                continue

            # ---------------- LINE COMMENT ----------------
            if mode == LINE_COMMENT:
                if ch == "\n":
                    # конец комментария — переводим накопленное
                    translated_inner = translate_buffer("comment")
                    result.append(translated_inner)
                    result.append("\n")
                    mode = NORMAL
                    i += 1
                    continue
                else:
                    buf.append(ch)
                    i += 1
                    continue

            # ---------------- BLOCK COMMENT ----------------
            if mode == BLOCK_COMMENT:
                if ch == "*" and i + 1 < n and text[i + 1] == "/":
                    # конец /* ... */
                    translated_inner = translate_buffer("comment")
                    result.append(translated_inner)
                    result.append("*/")
                    mode = NORMAL
                    i += 2
                    continue
                else:
                    buf.append(ch)
                    i += 1
                    continue

        # Хвостовые ситуации:
        if mode == LINE_COMMENT:
            # файл закончился внутри // комментария
            translated_inner = translate_buffer("comment")
            result.append(translated_inner)
        elif mode == BLOCK_COMMENT:
            # незакрытый /* ... – не трогаем, чтобы не сломать файл
            result.extend(buf)
        elif mode == STRING:
            # незакрытая строка — тоже не трогаем, небезопасно
            result.extend(buf)

        out = "".join(result)
        self.logger.info(
            f"[JAVA] Done {label}: {len(text)} -> {len(out)} chars"
        )
        return out

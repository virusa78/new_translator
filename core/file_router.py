# core/file_router.py
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .stats import Stats
from .string_translator import StringTranslator
from java_translator import JavaTranslator  # локальный модуль рядом с translate_project.py


__all__ = ["route_and_process_file"]


def route_and_process_file(
    src_root: Path,
    dst_root: Path,
    rel_path: Path,
    *,
    java_translator: JavaTranslator,
    string_translator: StringTranslator,  # пока не используем, но оставляем для будущих типов
    stats: Stats,
    logger: logging.Logger,
    verbose: bool = False,
) -> None:
    """
    Единая точка обработки одного файла.

    - Решает, надо ли файл переводить (сейчас только .java).
    - Делает RESUME: если целевой файл уже есть – не трогаем.
    - Отвечает за чтение/запись на диск и обновление статистики.
    - Внутри вызывает только text→text переводчики (JavaTranslator и т.п.).
    """
    src_path = src_root / rel_path
    dst_path = dst_root / rel_path

    stats.total_files += 1
    suffix = src_path.suffix.lower()

    # --- RESUME -----------------------------------------------------------
    if dst_path.exists():
        stats.skipped_files += 1
        if verbose:
            logger.info(f"[RESUME] Skip already processed file: {rel_path}")
        return

    try:
        # ------------------------------------------------------------------
        # 1) Java-файлы: гоняем через JavaTranslator (LLM дергается внутри)
        # ------------------------------------------------------------------
        if suffix == ".java":
            logger.info(f"[FILE] Start JAVA: {rel_path}")

            # читаем как текст
            text = src_path.read_text(encoding="utf-8", errors="replace")

            len_in = len(text)
            translated = java_translator.translate(text, file_label=str(rel_path))
            len_out = len(translated)

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_text(translated, encoding="utf-8", newline="")

            stats.translated_files += 1

            if verbose:
                logger.info(
                    f"[FILE] Done JAVA: {rel_path} "
                    f"(len_in={len_in}, len_out={len_out})"
                )
            return

        # ------------------------------------------------------------------
        # 2) MVP: всё остальное просто копируем как есть
        #    (XML/JSON/HTML/etc будем подключать позже отдельными агентами)
        # ------------------------------------------------------------------
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        stats.skipped_files += 1

        if verbose:
            logger.info(
                f"[FILE] Copied without translation (suffix={suffix}): {rel_path}"
            )

    except Exception as e:
        stats.error_files += 1
        msg = f"[ERROR] Translate {src_path}: {e}"
        # В verbose режиме логируем stacktrace, в обычном — только сообщение
        logger.error(msg, exc_info=verbose)
        stats.errors.append(msg)

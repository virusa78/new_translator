# core/file_router.py
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict
import logging

from core.stats import Stats

# Универсальный тип: любой переводчик, у которого есть translate(text: str) -> str
TranslatorLike = Callable[[str], str]


def route_and_process_file(
    src_root: Path,
    dst_root: Path,
    rel_path: Path,
    translators_by_ext: Dict[str, TranslatorLike],
    logger: logging.Logger,
    stats: Stats,
) -> None:
    """
    Единый FileRouter для всего проекта.

    - НЕ знает про конкретные языки (Java/HTML/...),
      только про расширения и "переводчики".
    - Всегда делает:
        read -> (optional translate) -> write
    """

    src_path = src_root / rel_path
    dst_path = dst_root / rel_path

    if not src_path.is_file():
        # На всякий случай, если в списке окажутся каталоги
        return

    stats.total_files += 1

    # Целевая папка
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    ext = rel_path.suffix.lower()
    translator = translators_by_ext.get(ext)

    # ------------------------------------------
    # РЕЗЮМЕ: если файл уже есть в output
    # ------------------------------------------
    if dst_path.exists() and translator is not None:
        logger.info(f"[RESUME] Skip already translated file: {dst_path}")
        stats.skipped_files += 1
        return

    # ------------------------------------------
    # Если переводчик не зарегистрирован для расширения —
    # просто копируем файл.
    # ------------------------------------------
    if translator is None:
        try:
            shutil.copy2(src_path, dst_path)
            stats.skipped_files += 1
        except Exception as e:
            msg = f"[ERROR] Copy {src_path} -> {dst_path}: {e}"
            logger.error(msg, exc_info=True)
            stats.error_files += 1
            stats.errors.append(msg)
        return

    # ------------------------------------------
    # Есть переводчик → работаем как text -> text
    # ------------------------------------------
    try:
        text = src_path.read_text(encoding="utf-8")
    except Exception as e:
        msg = f"[ERROR] Read {src_path}: {e}"
        logger.error(msg, exc_info=True)
        stats.error_files += 1
        stats.errors.append(msg)
        return

    # Пустой / пробельный файл — просто копия
    if not text.strip():
        try:
            dst_path.write_text(text, encoding="utf-8")
            stats.skipped_files += 1
        except Exception as e:
            msg = f"[ERROR] Write empty {dst_path}: {e}"
            logger.error(msg, exc_info=True)
            stats.error_files += 1
            stats.errors.append(msg)
        return

    try:
        translated = translator(text)  # КЛЮЧЕВОЕ: ЕДИНЫЙ ИНТЕРФЕЙС translate(str)->str
    except Exception as e:
        msg = f"[ERROR] Translate {src_path}: {e}"
        logger.error(msg, exc_info=True)
        stats.error_files += 1
        stats.errors.append(msg)
        return

    try:
        dst_path.write_text(translated, encoding="utf-8")
    except Exception as e:
        msg = f"[ERROR] Write {dst_path}: {e}"
        logger.error(msg, exc_info=True)
        stats.error_files += 1
        stats.errors.append(msg)
        return

    stats.translated_files += 1

# core/file_router.py
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


JAVA_EXTENSIONS = {".java"}


def ensure_parent_dir(path: Path) -> None:
    """
    Ensure that parent directory exists.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def route_and_process_file(
    src_root: Path,
    dst_root: Path,
    rel_path: Path,
    java_translator: Any,
    stats: Any,
    logger: Any,
) -> None:
    """
    Route a single file to the proper translation/copy logic and write result.

    For MVP:
    - .java → JavaTranslator.translate(text, file_label=...)
    - другие файлы → просто копируем (skip/RESUME)

    Atomic write:
    - if src_size > 10 KB → write to tmp file and then os.replace
    """
    src_path = src_root / rel_path
    dst_path = dst_root / rel_path

    stats.total_files += 1

    # RESUME: если целевой файл уже существует — пропускаем
    if dst_path.exists():
        logger.info(f"[RESUME] Skip already processed file: {rel_path}")
        stats.skipped_files += 1
        return

    suffix = src_path.suffix.lower()

    # --- Java files: use JavaTranslationAgent ---
    if suffix in JAVA_EXTENSIONS:
        try:
            text = src_path.read_text(encoding="utf-8")
        except Exception as e:
            msg = f"[ERROR] Read failed: {src_path}: {e}"
            logger.error(msg, exc_info=True)
            stats.error_files += 1
            stats.errors.append(msg)
            return

        logger.info(
            f"[JAVA] Translating {rel_path} (len={len(text)} chars)"
        )

        try:
            translated = java_translator.translate(
                text=text,
                file_label=str(rel_path),  # for logging / future heuristics
            )
        except Exception as e:
            msg = f"[ERROR] Translate {src_path}: {e}"
            logger.error(msg, exc_info=True)
            stats.error_files += 1
            stats.errors.append(msg)
            return

        # атомарная запись для файлов > 10 KB
        try:
            ensure_parent_dir(dst_path)
            if len(text) > 10_000:
                tmp_path = dst_path.with_suffix(dst_path.suffix + ".tmp")
                tmp_path.write_text(translated, encoding="utf-8")
                tmp_path.replace(dst_path)
            else:
                dst_path.write_text(translated, encoding="utf-8")

            stats.translated_files += 1
            stats.total_input_chars += len(text)
            stats.total_output_chars += len(translated)
            stats.total_words += len(translated.split())
        except Exception as e:
            msg = f"[ERROR] Write failed: {dst_path}: {e}"
            logger.error(msg, exc_info=True)
            stats.error_files += 1
            stats.errors.append(msg)

        return

    # --- Non-Java: just copy (MVP) ---
    try:
        ensure_parent_dir(dst_path)
        shutil.copy2(src_path, dst_path)
        logger.info(f"[COPY] {rel_path}")
        stats.skipped_files += 1
    except Exception as e:
        msg = f"[ERROR] Copy {src_path} -> {dst_path}: {e}"
        logger.error(msg, exc_info=True)
        stats.error_files += 1
        stats.errors.append(msg)

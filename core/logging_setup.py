# core/logging_setup.py
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(output_root: Path) -> logging.Logger:
    """
    Создаёт логгер 'translator', который пишет:
    - в stdout
    - в файл <output_root>/_translation_logs/translation.log

    Если логгер уже сконфигурирован (хендлеры есть) — просто возвращает его,
    чтобы не плодить дубликаты.
    """
    log_dir = output_root / "_translation_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "translation.log"

    logger = logging.getLogger("translator")
    logger.setLevel(logging.INFO)

    # Если хендлеры уже есть — не добавляем повторно
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    # Консоль
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Файл
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger.info(f"Logging to {log_path}")
    return logger

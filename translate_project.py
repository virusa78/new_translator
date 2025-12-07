#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Project translator MVP (Java + strings) with FileRouter.

Usage (llama.cpp):
    python translate_project.py \
        --input path/to/project \
        --output /path/to/output_dir \
        --backend llama \
        --llama-url http://localhost:8080/v1/chat/completions \
        --model gemma-3-4b-it \
        --workers 4 \
        --source-lang ru \
        --target-lang en
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path
from typing import Dict

from core.llm_client import LlamaCppClient, OllamaClient, BaseLLMClient
from core.string_translator import StringTranslator
from core.stats import Stats
from core.file_router import route_and_process_file
from core.logging_setup import setup_logger  # если нет — покажу ниже альтернативу

from java_translator import JavaTranslator


def prepare_input(input_path: Path, logger) -> Path:
    """
    MVP: только директории.
    Если нужен ZIP — можно потом добавить (как в старом скрипте).
    """
    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        sys.exit(1)
    if input_path.is_file():
        logger.error("MVP ожидает директорию, а не ZIP. Добавим ZIP позже.")
        sys.exit(1)
    return input_path


def iter_project_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def main():
    parser = argparse.ArgumentParser(
        description="Translate project files with local LLM (MVP: Java + strings)."
    )
    parser.add_argument("--input", required=True, help="Path to project directory.")
    parser.add_argument("--output", required=True, help="Path to output directory.")

    parser.add_argument(
        "--backend",
        choices=["llama", "ollama"],
        required=True,
        help="LLM backend: 'llama' for llama.cpp server, 'ollama' for Ollama.",
    )
    parser.add_argument(
        "--llama-url",
        default="http://localhost:8080/v1/chat/completions",
        help="llama.cpp chat completions URL (used if --backend=llama).",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434/api/generate",
        help="Ollama /api/generate URL (used if --backend=ollama).",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name or alias (llama.cpp alias or Ollama model tag).",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel worker threads.",
    )
    parser.add_argument(
        "--source-lang",
        default="ru",
        help="Source language code (e.g. ru, en, zh).",
    )
    parser.add_argument(
        "--target-lang",
        default="en",
        help="Target language code (e.g. en, tr, ru).",
    )
    parser.add_argument(
        "--ollama-options",
        type=str,
        default="",
        help="JSON string with extra Ollama 'options' (only if --backend=ollama).",
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    # ---------- logging ----------
    try:
        from core.logging_setup import setup_logger as _setup_logger
        logger = _setup_logger(output_root)
    except Exception:
        # Фоллбэк, если logging_setup модуля нет
        import logging

        log_path = output_root / "_translation_logs"
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / "translation.log"

        logger = logging.getLogger("translator")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
            )
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(fmt)
            logger.addHandler(ch)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)

    logger.info(f"Input:  {input_path}")
    logger.info(f"Output: {output_root}")
    logger.info(f"Backend: {args.backend}")
    logger.info(f"Model:   {args.model}")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Lang:    {args.source_lang} → {args.target_lang}")

    src_root = prepare_input(input_path, logger)

    # ---------- LLM client ----------
    if args.backend == "llama":
        client: BaseLLMClient = LlamaCppClient(
            url=args.llama_url,
            model=args.model,
            timeout=600,
        )
        logger.info(f"llama.cpp URL: {args.llama_url}")
    else:
        options = {}
        if args.ollama_options:
            try:
                options = json.loads(args.ollama_options)
            except Exception as e:
                logger.error(f"Failed to parse --ollama-options JSON: {e}")
        client = OllamaClient(
            url=args.ollama_url,
            model=args.model,
            timeout=600,
            options=options,
        )
        logger.info(f"Ollama URL: {args.ollama_url}")
        if options:
            logger.info(f"Ollama options: {options}")

    # ---------- Stats + glossary ----------
    stats = Stats()
    glossary_dir = output_root / "_translation_logs"
    glossary_dir.mkdir(parents=True, exist_ok=True)
    glossary_path = glossary_dir / "glossary_suggestions.tsv"
    if not glossary_path.exists():
        glossary_path.write_text("# original\ttranslation\n", encoding="utf-8")

    # ---------- Shared StringTranslator ----------
    string_translator = StringTranslator(
        client=client,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        stats=stats,
        glossary_path=glossary_path,
    )

    # ---------- JavaTranslator ----------
    java_translator = JavaTranslator(
        string_translator=string_translator,
        stats=stats,
        logger=logger,
    )

    # ---------- File router config ----------
    # ЕДИНЫЙ контракт: .java → объект с методом translate(text:str)->str
    translators_by_ext: Dict[str, callable] = {
        ".java": java_translator.translate,
        # потом добавим ".html": html_translator.translate, и т.д.
    }

    # ---------- Собираем список файлов ----------
    files = [p.relative_to(src_root) for p in iter_project_files(src_root)]
    logger.info(f"Discovered {len(files)} files to process.")

    start_time = time.time()

    def worker(rel_path: Path):
        route_and_process_file(
            src_root=src_root,
            dst_root=output_root,
            rel_path=rel_path,
            translators_by_ext=translators_by_ext,
            logger=logger,
            stats=stats,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(worker, files))

    end_time = time.time()
    wall_time = end_time - start_time
    llm_time = stats.llm_time_seconds or 1e-9
    words_per_sec = stats.total_words / llm_time

    logger.info("-------------- TRANSLATION SUMMARY --------------")
    logger.info(f"Total files:          {stats.total_files}")
    logger.info(f"Translated files:     {stats.translated_files}")
    logger.info(f"Skipped (copied/res): {stats.skipped_files}")
    logger.info(f"Files with errors:    {stats.error_files}")
    logger.info(f"Total input chars:    {stats.total_input_chars}")
    logger.info(f"Total output chars:   {stats.total_output_chars}")
    logger.info(f"Total words (approx): {stats.total_words}")
    logger.info(f"LLM time (s):         {llm_time:.2f}")
    logger.info(f"Wall time (s):        {wall_time:.2f}")
    logger.info(f"Throughput:           {words_per_sec:.2f} words/sec (LLM time)")

    if stats.errors:
        logger.info("Errors encountered:")
        for e in stats.errors:
            logger.info(f"  {e}")


if __name__ == "__main__":
    main()


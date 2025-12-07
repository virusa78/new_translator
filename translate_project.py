#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVP-переводчик исходников:

- backend: llama.cpp или Ollama
- поддержка:
    * перевода отдельных строк (StringTranslator)
    * перевода .java файлов (строки + комментарии)
- sanity-check перед массовым переводом:
    * tests/sanity_check.txt
    * tests/sanity_check.java
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, Any

from llm_client import LlamaCppClient, OllamaClient, BaseLLMClient
from stats import Stats
from string_translator import StringTranslator
from java_translator import JavaTranslator
from sanity_check import run_all as run_sanity_all


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("translator")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


def build_client(args: argparse.Namespace, logger: logging.Logger) -> BaseLLMClient:
    if args.backend == "llama":
        logger.info(f"Using llama.cpp backend at {args.llama_url}")
        return LlamaCppClient(url=args.llama_url, model=args.model)
    else:
        options: Dict[str, Any] = {}
        if args.ollama_options:
            import json

            try:
                options = json.loads(args.ollama_options)
            except Exception as e:
                logger.error(f"Failed to parse --ollama-options JSON: {e}")
        logger.info(f"Using Ollama backend at {args.ollama_url}, options={options}")
        return OllamaClient(
            url=args.ollama_url,
            model=args.model,
            options=options,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MVP project translator (Java + string) using local LLM."
    )
    parser.add_argument("--input", required=True, help="Path to project directory.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output directory (will be created if not exists).",
    )

    parser.add_argument(
        "--backend",
        choices=["llama", "ollama"],
        required=True,
        help="LLM backend: 'llama' for llama.cpp, 'ollama' for Ollama.",
    )
    parser.add_argument(
        "--llama-url",
        default="http://localhost:8080/v1/chat/completions",
        help="llama.cpp chat completions URL.",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434/api/generate",
        help="Ollama /api/generate URL.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name or alias (llama.cpp alias or Ollama model tag).",
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
        "--no-sanity-check",
        action="store_true",
        help="Skip sanity-check before translation.",
    )
    parser.add_argument(
        "--sanity-strict",
        action="store_true",
        help="Treat sanity warnings as fatal (abort translation).",
    )

    parser.add_argument(
        "--ollama-options",
        type=str,
        default="",
        help="JSON string with extra Ollama 'options' (only if --backend=ollama).",
    )

    args = parser.parse_args()

    logger = setup_logger()

    input_root = Path(args.input).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    if not input_root.is_dir():
        logger.error(f"Input path is not a directory: {input_root}")
        sys.exit(1)

    logger.info(f"Input:  {input_root}")
    logger.info(f"Output: {output_root}")
    logger.info(
        f"Backend: {args.backend}, model={args.model}, lang={args.source_lang}->{args.target_lang}"
    )

    client = build_client(args, logger)

    # --- Sanity check -----------------------------------------------------

    if not args.no_sanity_check:
        sanity = run_sanity_all(
            client=client,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            logger=logger,
            output_root=output_root,
        )

        has_fail = any(r.status == "fail" for r in sanity.values())
        has_warn = any(r.status == "warn" for r in sanity.values())

        if has_fail:
            logger.error(
                "Sanity check FAILED (status=fail). See sanity_report.json for details."
            )
            sys.exit(1)
        if has_warn and args.sanity_strict:
            logger.error(
                "Sanity check produced warnings and --sanity-strict is enabled. Aborting."
            )
            sys.exit(1)
        if not sanity:
            logger.warning(
                "No sanity checks were performed (no test files). Proceeding anyway."
            )
    else:
        logger.info("Sanity-check is disabled via --no-sanity-check.")

    # --- Основной перевод -------------------------------------------------

    stats = Stats()
    glossary_path = output_root / "_translation_logs" / "glossary_suggestions.tsv"
    string_translator = StringTranslator(
        client=client,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        stats=stats,
        glossary_path=glossary_path,
    )
    java_translator = JavaTranslator(
        string_translator=string_translator,
        stats=stats,
        logger=logger,
    )

    logger.info("Starting project translation (MVP: Java + copying others)...")

    for src in input_root.rglob("*"):
        if src.is_dir():
            continue

        rel = src.relative_to(input_root)
        dst = output_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        stats.total_files += 1

        if src.suffix.lower() == ".java":
            logger.info(f"[JAVA] Translating {rel}")
            java_translator.translate_file(src, dst)
        else:
            # MVP: просто копируем все не-Java файлы
            shutil.copy2(src, dst)
            stats.skipped_files += 1

    # --- summary ----------------------------------------------------------

    logger.info("-------------- TRANSLATION SUMMARY --------------")
    logger.info(f"Total files:          {stats.total_files}")
    logger.info(f"Translated (Java):    {stats.translated_files}")
    logger.info(f"Skipped (copied):     {stats.skipped_files}")
    logger.info(f"Files with errors:    {stats.error_files}")
    logger.info(f"Total input chars:    {stats.total_input_chars}")
    logger.info(f"Total output chars:   {stats.total_output_chars}")
    logger.info(f"Total words (approx): {stats.total_words}")
    logger.info(f"LLM time (s):         {stats.llm_time_seconds:.2f}")

    if stats.errors:
        logger.info("Errors encountered:")
        for e in stats.errors:
            logger.info(f"  {e}")


if __name__ == "__main__":
    main()

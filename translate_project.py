from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List

from tqdm import tqdm

from core.llm_client import LlamaCppClient, OllamaClient, BaseLLMClient
from core.logging_setup import setup_logger
from core.stats import Stats
from core.string_translator import StringTranslator
from core.file_router import route_and_process_file
from java_translator import JavaTranslator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Offline source-code translator (MVP: Java + string translation) "
            "using local LLM (llama.cpp or Ollama)."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to project directory or ZIP archive.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output directory (will be created if not exists).",
    )
    parser.add_argument(
        "--backend",
        choices=["llama", "ollama"],
        required=True,
        help="LLM backend: 'llama' for llama.cpp server, 'ollama' for Ollama.",
    )
    parser.add_argument(
        "--llama-url",
        default="http://localhost:8080/v1/chat/completions",
        help="llama.cpp /v1/chat/completions URL (used if --backend=llama).",
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
    return parser.parse_args()


def prepare_input(input_path: Path, logger: logging.Logger) -> Path:
    """
    If input is a ZIP, unzip to a temp dir and return that path.
    Otherwise return the input path unchanged.
    """
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        tmp_dir = Path(tempfile.mkdtemp(prefix="llm_translate_"))
        logger.info(f"Unzipping {input_path} to {tmp_dir}")
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(tmp_dir)
        return tmp_dir
    return input_path


def iter_project_files(root: Path) -> List[Path]:
    """Return list of all files (relative paths) under root."""
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            files.append(p.relative_to(root))
    return files


def build_llm_client(args: argparse.Namespace, logger: logging.Logger) -> BaseLLMClient:
    if args.backend == "llama":
        client: BaseLLMClient = LlamaCppClient(
            url=args.llama_url,
            model=args.model,
        )
        logger.info(f"Backend: llama.cpp url={args.llama_url} model={args.model}")
        return client

    # backend == "ollama"
    options: dict = {}
    if args.ollama_options:
        try:
            options = json.loads(args.ollama_options)
        except Exception as e:
            logger.error(f"Failed to parse --ollama-options JSON: {e}")
    client = OllamaClient(
        url=args.ollama_url,
        model=args.model,
        options=options,
    )
    logger.info(
        f"Backend: ollama url={args.ollama_url} model={args.model} options={options}"
    )
    return client


def main() -> None:
    args = parse_args()

    input_path = Path(args.input).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(output_root)

    logger.info(f"Input:  {input_path}")
    logger.info(f"Output: {output_root}")
    logger.info(f"Backend: {args.backend}, model={args.model}, workers={args.workers}")
    logger.info(f"Lang: {args.source_lang} → {args.target_lang}")

    client = build_llm_client(args, logger)
    stats = Stats()

    # glossary setup (used by StringTranslator)
    glossary_path = output_root / "_translation_logs" / "glossary_suggestions.tsv"
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    if not glossary_path.exists():
        glossary_path.write_text("# original\ttranslation\n", encoding="utf-8")

    string_translator = StringTranslator(
        client=client,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        stats=stats,
        glossary_path=glossary_path,
    )

    java_translator = JavaTranslator(
        string_translator=string_translator,
        logger=logger,
    )

    src_root = prepare_input(input_path, logger)
    if not src_root.is_dir():
        logger.error(f"Prepared input root is not a directory: {src_root}")
        sys.exit(1)

    files = iter_project_files(src_root)
    logger.info(f"Discovered {len(files)} files to process.")

    start_time = time.time()

    def worker(rel_path: Path) -> None:
        logger.info(f"[FILE] Start: {rel_path}")
        route_and_process_file(
            src_root=src_root,
            dst_root=output_root,
            rel_path=rel_path,
            java_translator=java_translator,
            #string_translator=string_translator,
            stats=stats,
            logger=logger,
        )
        logger.info(f"[FILE] Done:  {rel_path}")

    use_tqdm = sys.stderr.isatty()

    if use_tqdm:
        logger.info(
            f"Progress: using tqdm over {len(files)} files, workers={args.workers}"
        )
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(
                tqdm(
                    pool.map(worker, files),
                    total=len(files),
                    desc="Translating files",
                    unit="file",
                )
            )
    else:
        logger.info(
            f"Progress: no TTY detected, running without tqdm, workers={args.workers}"
        )
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(worker, files))

    wall_time = time.time() - start_time
    stats.log_summary(logger, wall_time)


if __name__ == "__main__":
    main()

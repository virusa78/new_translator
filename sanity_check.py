# sanity_check.py
from __future__ import annotations

from pathlib import Path
import logging
from typing import Dict

from llm_client import BaseLLMClient
from stats import Stats
from string_translator import StringTranslator
from java_translator import JavaTranslator
from qa_report import (
    SanityResult,
    qa_plain_string,
    qa_code_java,
    write_report,
)


def run_all(
    client: BaseLLMClient,
    source_lang: str,
    target_lang: str,
    logger: logging.Logger,
    output_root: Path,
) -> SanityResult:
    """
    Запускает sanity-check для STRING и JAVA режимов.
    Возвращает карту результатов.
    """
    base_dir = Path(__file__).resolve().parent
    tests_dir = base_dir / "tests"

    result: SanityResult = {}

    stats = Stats()
    glossary_path = output_root / "_translation_logs" / "glossary_suggestions.tsv"
    string_translator = StringTranslator(
        client=client,
        source_lang=source_lang,
        target_lang=target_lang,
        stats=stats,
        glossary_path=glossary_path,
    )

    # --- STRING -----------------------------------------------------------

    txt_path = tests_dir / "sanity_check.txt"
    if txt_path.exists():
        logger.info(f"[SANITY] String check using {txt_path}")
        orig = txt_path.read_text(encoding="utf-8").strip()
        translated = string_translator.translate_string(orig)
        r = qa_plain_string(orig, translated, source_lang, target_lang)
        result["string_simple"] = r
    else:
        logger.warning(f"[SANITY] Missing {txt_path}, skipping string sanity check.")

    # --- JAVA -------------------------------------------------------------

    java_path = tests_dir / "sanity_check.java"
    if java_path.exists():
        logger.info(f"[SANITY] Java check using {java_path}")
        orig_java = java_path.read_text(encoding="utf-8")

        java_translator = JavaTranslator(
            string_translator=string_translator,
            stats=stats,
            logger=logger,
        )
        translated_java = java_translator.translate_text(orig_java)
        r_java = qa_code_java(orig_java, translated_java)
        result["java_file"] = r_java
    else:
        logger.warning(f"[SANITY] Missing {java_path}, skipping Java sanity check.")

    # --- summary + запись отчёта -----------------------------------------

    if result:
        report_path = write_report(result, output_root)
        logger.info(f"[SANITY] Report written to {report_path}")

        for name, r in result.items():
            logger.info(
                f"[SANITY] {name}: status={r.status}, issues={[i.code for i in r.issues]}"
            )
    else:
        logger.warning("[SANITY] No sanity checks were run (no test files).")

    return result

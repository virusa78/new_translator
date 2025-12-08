# core/stats.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import logging


@dataclass
class Stats:
    total_files: int = 0
    translated_files: int = 0
    skipped_files: int = 0
    error_files: int = 0

    total_input_chars: int = 0
    total_output_chars: int = 0
    total_words: int = 0

    llm_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def log_summary(self, logger: logging.Logger, wall_time: float) -> None:
        logger.info("-------------- TRANSLATION SUMMARY --------------")
        logger.info(f"Total files:          {self.total_files}")
        logger.info(f"Translated files:     {self.translated_files}")
        logger.info(f"Skipped (copied/res): {self.skipped_files}")
        logger.info(f"Files with errors:    {self.error_files}")
        logger.info(f"Total input chars:    {self.total_input_chars}")
        logger.info(f"Total output chars:   {self.total_output_chars}")
        logger.info(f"Total words (approx): {self.total_words}")
        logger.info(f"LLM time (s):         {self.llm_time_seconds:.2f}")
        logger.info(f"Wall time (s):        {wall_time:.2f}")

        if self.llm_time_seconds > 0:
            wps = self.total_words / self.llm_time_seconds
            logger.info(f"Throughput:           {wps:.2f} words/sec (LLM time)")

        if self.errors:
            logger.info("Errors encountered:")
            for e in self.errors:
                logger.info(f"  {e}")

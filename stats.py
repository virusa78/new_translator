# stats.py
from dataclasses import dataclass, field
from typing import List


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

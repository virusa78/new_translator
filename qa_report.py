# qa_report.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

import json
import re


@dataclass
class QaIssue:
    code: str
    message: str


@dataclass
class QaCheckResult:
    status: str  # "ok" | "warn" | "fail"
    issues: List[QaIssue]
    details: Dict[str, Any]


SanityResult = Dict[str, QaCheckResult]

# --- эвристики ------------------------------------------------------------

BANNED_SUBSTRINGS = [
    "OpenAI",
    "ChatGPT",
    "LLM",
    "API",
    "Key improvements",
    "The code now",
    "Error generating text",
    "In this example",
    "Below is",
]


CRITICAL_ISSUES = {
    "empty_translation",
    "banned_token",
    "structure_changed",
}


def _check_banned(text: str) -> List[QaIssue]:
    issues: List[QaIssue] = []
    for token in BANNED_SUBSTRINGS:
        if token in text:
            issues.append(
                QaIssue(
                    code="banned_token",
                    message=f"Banned token '{token}' found in translation.",
                )
            )
    return issues


def _sentence_count(s: str) -> int:
    # Очень грубо, но для sanity достаточно
    parts = re.split(r"[.!?]+", s)
    return sum(1 for p in parts if p.strip())


# --- plain string ---------------------------------------------------------


def qa_plain_string(
    orig: str, translated: str, source_lang: str, target_lang: str
) -> QaCheckResult:
    issues: List[QaIssue] = []
    details: Dict[str, Any] = {
        "orig_len": len(orig),
        "translated_len": len(translated),
    }

    if not translated.strip():
        issues.append(
            QaIssue(code="empty_translation", message="Translated string is empty.")
        )

    issues.extend(_check_banned(translated))

    orig_sent = _sentence_count(orig)
    tr_sent = _sentence_count(translated)

    details["orig_sentences"] = orig_sent
    details["translated_sentences"] = tr_sent

    if tr_sent > orig_sent + 2:
        issues.append(
            QaIssue(
                code="too_many_sentences",
                message=(
                    f"Translated string has suspiciously more sentences: "
                    f"{tr_sent} vs {orig_sent}."
                ),
            )
        )

    status = "ok"
    if any(i.code in CRITICAL_ISSUES for i in issues):
        status = "fail"
    elif issues:
        status = "warn"

    return QaCheckResult(status=status, issues=issues, details=details)


# --- Java skeletal comparison ---------------------------------------------


def _mask_java_skeleton(text: str) -> tuple[str, int, int]:
    """
    Возвращает:
      - skeleton: строка, где строки/комменты заменены на маркеры __STRi__/__CMTj__
      - count_strings
      - count_comments
    """
    i = 0
    n = len(text)
    out: List[str] = []
    str_count = 0
    cmt_count = 0

    while i < n:
        ch = text[i]

        # line comment
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            out.append(f"__CMT{cmt_count}__")
            cmt_count += 1
            i += 2
            while i < n and text[i] not in "\r\n":
                i += 1
            if i < n:
                out.append(text[i])  # перенос строки
                i += 1
            continue

        # block comment
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            out.append(f"__CMT{cmt_count}__")
            cmt_count += 1
            i += 2
            end = text.find("*/", i)
            if end == -1:
                break
            i = end + 2
            continue

        # string literal
        if ch == '"':
            out.append(f"__STR{str_count}__")
            str_count += 1
            i += 1
            escaped = False
            while i < n:
                c = text[i]
                if escaped:
                    escaped = False
                    i += 1
                    continue
                if c == "\\":
                    escaped = True
                    i += 1
                    continue
                if c == '"':
                    i += 1
                    break
                i += 1
            continue

        # char literal — пропускаем как обычный символ, менять не должны
        if ch == "'" and i + 1 < n:
            out.append("'")
            i += 1
            escaped = False
            while i < n:
                c = text[i]
                if escaped:
                    escaped = False
                    i += 1
                    continue
                if c == "\\":
                    escaped = True
                    i += 1
                    continue
                if c == "'":
                    i += 1
                    break
                i += 1
            out.append("'")
            continue

        out.append(ch)
        i += 1

    return "".join(out), str_count, cmt_count


def qa_code_java(orig: str, translated: str) -> QaCheckResult:
    issues: List[QaIssue] = []
    details: Dict[str, Any] = {}

    if not translated.strip():
        issues.append(
            QaIssue(code="empty_translation", message="Translated Java file is empty.")
        )

    sk_orig, str_orig, cmt_orig = _mask_java_skeleton(orig)
    sk_tr, str_tr, cmt_tr = _mask_java_skeleton(translated)

    details["strings_orig"] = str_orig
    details["strings_translated"] = str_tr
    details["comments_orig"] = cmt_orig
    details["comments_translated"] = cmt_tr

    if sk_orig != sk_tr:
        issues.append(
            QaIssue(
                code="structure_changed",
                message="Code skeleton changed between original and translation.",
            )
        )

    if str_orig != str_tr:
        issues.append(
            QaIssue(
                code="string_count_mismatch",
                message="Number of string literals changed.",
            )
        )

    if cmt_orig != cmt_tr:
        issues.append(
            QaIssue(
                code="comment_count_mismatch",
                message="Number of comments changed.",
            )
        )

    issues.extend(_check_banned(translated))

    status = "ok"
    if any(i.code in CRITICAL_ISSUES for i in issues):
        status = "fail"
    elif issues:
        status = "warn"

    return QaCheckResult(status=status, issues=issues, details=details)


# --- запись отчёта --------------------------------------------------------


def write_report(result: SanityResult, output_root: Path) -> Path:
    out_dir = output_root / "_translation_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "sanity_report.json"

    serializable: Dict[str, Any] = {}
    for name, check in result.items():
        serializable[name] = {
            "status": check.status,
            "issues": [asdict(i) for i in check.issues],
            "details": check.details,
        }

    path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

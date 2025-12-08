# Project Context – Local Source Code Translator (MVP: Java + Strings)

Language: EN (token-efficient)

## Goal

Local, deterministic translation of source code repositories using a local LLM
(llama.cpp or Ollama). MVP translates Java source files and standalone strings:

- Only comments and string literals are translated.
- Code structure, identifiers, and syntax remain unchanged.
- Strong anti-hallucination and sanity-check layer.
- Single place for file IO and atomic writes for big files.

---

## High-level Architecture

### 1. Orchestrator CLI

**File:** `translate_project.py`  
**Role:** Entry point, overall coordinator.

**Responsibilities:**

- Parse CLI args:
  - `--input`, `--output`
  - `--backend` (`llama` / `ollama`)
  - `--llama-url`, `--ollama-url`
  - `--model`
  - `--workers`
  - `--source-lang`, `--target-lang`
- Initialize:
  - output directory,
  - logger via `setup_logger`,
  - `Stats`,
  - `LLMClient` (`LlamaCppClient` or `OllamaClient`),
  - `StringTranslator`,
  - `JavaTranslator`.
- Discover files under `--input` (`rglob`).
- Run per-file translation via `core.file_router.route_and_process_file(...)`
  inside `ThreadPoolExecutor` with `tqdm` progress over files.
- At the end:
  - Log translation summary from `Stats`.
  - (Later) run sanity checks and QA map.

**Key functions:**

- `main() -> None`
  - Full lifecycle of one translation run.
- `worker(rel_path: Path) -> None`
  - Wrapper calling `route_and_process_file` for one file.

---

### 2. LLM Client Layer

**File:** `core/llm_client.py`

**Classes:**

- `class BaseLLMClient:`
  - `translate(self, system_prompt: str, user_prompt: str) -> tuple[str, float]`
    - Abstract interface, returns `(text, dt_seconds)`.

- `class LlamaCppClient(BaseLLMClient):`
  - Fields: `url: str`, `model: str`, `timeout: int = 600`
  - `translate(...)`:
    - POST to `/v1/chat/completions`.
    - Payload:
      - `model`
      - `messages = [{"role": "system"}, {"role": "user"}]`
      - `temperature = 0.0`
    - Handles:
      - HTTP != 200 → `RuntimeError`
      - context overflow messages → `ExceedContextSizeError`
    - Logs request/response timing at higher layer (logger).

- `class OllamaClient(BaseLLMClient):`
  - Fields: `url: str`, `model: str`, `timeout: int = 600`, `options: dict | None`
  - `translate(...)`:
    - POST to `/api/generate`.
    - Single `prompt` with System/User/Assistant sections.
    - Returns `data["response"]`.

**File:** `core/errors.py`

- `class ExceedContextSizeError(RuntimeError):`
  - Signals that model context window was exceeded.

---

### 3. String Translation Layer

**File:** `core/string_translator.py`

**Role:** Safely translate *single* human-facing strings with caching and stats.

**Key elements:**

- Helper functions (internal API):
  - `is_human_visible_string(s: str) -> bool`
    - Heuristic: non-empty, not purely key/path, likely user-facing.
  - `build_system_prompt(source_lang: str, target_lang: str) -> str`
    - Strict translation system prompt (no explanations, preserve escapes).
  - `build_user_prompt_for_string(text: str, source_lang: str, target_lang: str) -> str`
    - “Translate ONLY this string” style, no extra output.

- `class StringTranslator:`
  - Fields:
    - `client: BaseLLMClient`
    - `source_lang: str`
    - `target_lang: str`
    - `stats: Stats`
    - `glossary_path: Path`
    - `cache: dict[str, str]`
    - `system_prompt: str` (prebuilt once)
  - Methods:
    - `translate(self, s: str) -> str`
      - If in cache → return cached.
      - If not human-visible → return as-is, cache.
      - Build user prompt, call `client.translate(system_prompt, user_prompt)`.
      - Strip outer quotes, update `stats`.
      - Append `orig -> translated` pair to `glossary_suggestions.tsv`.

---

### 4. Stats and Logging

**File:** `core/stats.py`

- `@dataclass class Stats:`
  - Fields:
    - `total_files: int`
    - `translated_files: int`
    - `skipped_files: int`
    - `error_files: int`
    - `total_input_chars: int`
    - `total_output_chars: int`
    - `total_words: int`
    - `llm_time_seconds: float`
    - `errors: list[str]`
  - Optional helper:
    - `log_summary(self, logger) -> None`
      - Prints final summary block.

**File:** `core/logging_setup.py`

- `setup_logger(dst_root: Path, verbose: bool = True) -> logging.Logger`
  - Creates `_translation_logs/translation.log`.
  - Adds stream handler (console) + file handler.
  - Formats timestamps and levels.

---

### 5. File Router (single IO owner)

**File:** `core/file_router.py`

**Role:** Map files to translators, handle IO, RESUME, atomic writes.

**Key function:**

- `route_and_process_file(
    src_root: Path,
    dst_root: Path,
    rel_path: Path,
    java_translator: JavaTranslator,
    stats: Stats,
    logger: logging.Logger,
) -> None`

**Logic:**

1. Build `src_path = src_root / rel_path`, `dst_path = dst_root / rel_path`.
2. If `dst_path` exists → `stats.skipped_files += 1`, log RESUME skip.
3. If file is not Java yet:
   - For MVP: copy as-is (binary or text) and mark skipped.
4. If `rel_path.suffix == ".java"`:
   - Read full text (UTF-8).
   - Call `java_translator.translate(text) -> translated_text`.
   - If file size > 10 KB:
     - Write to `dst_tmp = dst_path.with_suffix(".tmp")`, then `rename` → `dst_path`.
   - Else:
     - Write directly to `dst_path`.
   - Update `Stats`:
     - `translated_files += 1`
     - `total_input_chars`, `total_output_chars`, `total_words`, `llm_time_seconds`.
5. On any exception:
   - `error_files += 1`, append readable message to `stats.errors`.

---

### 6. Java Translation Module

**File:** `java/java_translator.py`

**Role:** Translate Java source text (comments + string literals) without touching structure.

**Class:**

- `class JavaTranslator:`
  - Fields:
    - `string_translator: StringTranslator`
    - `logger: logging.Logger`
  - Methods:
    - `translate(self, text: str) -> str`
      - Performs single-pass scan over `text` (char-by-char or token-by-token).
      - Identifies zones:
        - Double-quoted string literals `"..."` (with escape handling).
        - Line comments `//...`.
        - Block comments `/* ... */`, `/** ... */`.
      - Excludes:
        - Char literals `'a'`, `'\n'`, etc.
      - For each zone:
        - Extract inner text.
        - Call `self.string_translator.translate(inner_text)`.
        - Reassemble: same delimiters, spacing, and code.
      - Logs start/end:
        - `[JAVA] Translating <rel_path> (len=... chars)`.
      - Returns full translated Java file as string.

---

### 7. Sanity Check (design, can be implemented later)

**File:** `sanity/sanity_runner.py`

**Key ideas:**

- Use same `StringTranslator`, `JavaTranslator`, `LLMClient` as production.
- Tests:
  - `string_simple`:
    - Input: `tests/sanity_check.txt`.
    - Check:
      - Banned tokens,
      - Sentence count ratio,
      - Length ratio.
  - `java_file`:
    - Input: `tests/sanity_check.java`.
    - Compare:
      - Number of string literals (before/after).
      - Number of comments.
      - Code skeleton (Java source with strings/comments stripped).
      - Banned tokens.
- Output: `sanity_report.json` with structure like:

  ```json
  {
    "string_simple": {
      "status": "fail" | "ok",
      "issues": [ { "code": "...", "message": "..." } ],
      "details": { ... }
    },
    "java_file": { ... }
  }

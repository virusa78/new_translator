
# Codebase: Python, .venv   
# Translation Agents and Functions (MVP: Java + Strings)

Language: EN.

---

## 1. Orchestrator CLI Agent

**Module:** `translate_project.py`  
**Role:** top-level coordinator.

### Responsibilities

- Parse CLI args.
- Prepare input/output dirs.
- Init logger, Stats, LLM client.
- Init StringTranslator and JavaTranslator.
- Enumerate project files (relative paths).
- Run file processing in ThreadPoolExecutor with optional tqdm.
- At the end, call `Stats.log_summary()`.

### Key functions (module)

- `parse_args() -> argparse.Namespace`  
  Parse CLI options.

- `prepare_input(input_path: Path, logger: logging.Logger) -> Path`  
  Accept path or ZIP; unzip if needed.

- `iter_project_files(root: Path) -> List[Path]`  
  Collect all file paths under root (relative).

- `build_llm_client(args, logger) -> BaseLLMClient`  
  Create `LlamaCppClient` or `OllamaClient` based on `--backend`.

- `main() -> None`  
  Glue logic: initialization, workers, progress, summary.

---

## 2. File Router Agent

**Module:** `core/file_router.py`  
**Role:** single place for IO + per-file routing.

### Responsibilities

- Compute `src_path` and `dst_path` from roots + `rel_path`.
- Resume logic: if `dst_path` exists → skip.
- For MVP:
  - Non-text / non-Java → copy as-is.
  - `.java` → call JavaTranslator.
- Record Stats changes:
  - `total_files`, `translated_files`, `skipped_files`, `error_files`.
- Guard all IO with try/except and log errors.

### Key functions (module)

- `is_text_file(path: Path) -> bool`  
  Heuristic to detect text files (e.g. by extension).

- `route_and_process_file(src_root: Path, dst_root: Path, rel_path: Path, java_translator: JavaTranslator, stats: Stats, logger: logging.Logger) -> None`  
  Single entry point used by workers in `translate_project.py`.

---

## 3. LLM Client Agent

**Module:** `core/llm_client.py`  
**Role:** transport to llama.cpp / Ollama.

### Classes and methods

- `class BaseLLMClient`  
  - `translate(system_prompt: str, user_prompt: str) -> tuple[str, float]`  
    Abstract interface: return text + latency seconds.

- `class LlamaCppClient(BaseLLMClient)`  
  - Fields: `url`, `model`, `timeout`.  
  - `translate(system_prompt, user_prompt)`  
    Calls `/v1/chat/completions`, logs HTTP code and time, detects context overflow and raises `ExceedContextSizeError`.

- `class OllamaClient(BaseLLMClient)`  
  - Fields: `url`, `model`, `timeout`, `options`.  
  - `translate(system_prompt, user_prompt)`  
    Calls `/api/generate`, returns `response` text + latency.

---

## 4. String Translator Agent

**Module:** `core/string_translator.py`  
**Role:** safe translation of a single string with caching + stats.

### Responsibilities

- Store reference to:
  - `BaseLLMClient`,
  - language codes,
  - shared `Stats`,
  - `glossary_path`.
- Prebuild strict system prompt (code-oriented).
- Cache `orig → translated`.
- Decide whether string is human-visible (heuristics).
- Call LLM client and update Stats:
  - `total_input_chars`, `total_output_chars`,
  - `total_words`, `llm_time_seconds`.
- Append pairs to `glossary_suggestions.tsv`.

### Key functions / methods (module)

- `is_human_visible_string(text: str) -> bool`  
  Utility heuristic for keys/paths.

- `class StringTranslator`  
  - `__init__(client: BaseLLMClient, source_lang: str, target_lang: str, stats: Stats, glossary_path: Path)`  
    Save config, prepare system prompt, init cache.
  - `translate_string(text: str) -> str`  
    Main API: string → string (possibly unchanged), uses cache and LLM.

---

## 5. Java Translation Agent

**Module:** `java_translator.py`  
**Role:** translate Java comments and string literals only.

### Responsibilities

- Work purely in memory: no file IO.
- Parse Java as text in a single left-to-right pass.
- Detect lexical zones:
  - Line comments: `// ...`.
  - Block comments: `/* ... */`, `/** ... */`.
  - String literals: `"..."` (handle escapes and multi-line).
  - Char literals: `'a'`, `'\n'` – must be preserved.
- For each comment/string:
  - Extract payload.
  - Call `StringTranslator.translate_string()`.
  - Re-assemble tokens with original delimiters.
- Produce new Java source text with same skeleton.

### Key class and method

- `class JavaTranslator`  
  - `__init__(string_translator: StringTranslator, logger: logging.Logger)`  
    Store collaborators and logger.
  - `translate(text: str, file_label: str | None = None) -> str`  
    Main API used by File Router. `file_label` is used only for log/debug.

---

## 6. Stats + Glossary Agent

**Module:** `core/stats.py`  
**Role:** central statistics and error store.

### Key dataclass and methods

- `@dataclass class Stats`  
  Fields:
  - `total_files: int`
  - `translated_files: int`
  - `skipped_files: int`
  - `error_files: int`
  - `total_input_chars: int`
  - `total_output_chars: int`
  - `total_words: int`
  - `llm_time_seconds: float`
  - `errors: list[str]`
- `Stats.log_summary(logger: logging.Logger, wall_time: float) -> None`  
  Logs final counters, throughput and error list.

*(Glossary file handling – opening and appending – is implemented in `translate_project.py` and `StringTranslator`.)*

---

## 7. Logging Agent

**Module:** `core/logging_setup.py`  
**Role:** consistent logger configuration.

### Key function

- `setup_logger(output_root: Path) -> logging.Logger`  
  - Creates `_translation_logs/translation.log` under output root.
  - Creates logger `translator`.
  - Adds console + file handlers with unified format.
  - Safe to call once per process (reuses existing handlers).

---

## 8. Error Types

**Module:** `core/errors.py`  

- `class ExceedContextSizeError(RuntimeError)`  
  - Raised by `LlamaCppClient.translate()` when llama.cpp reports context overflow.
  - Handled by higher-level code where chunking/strategy will be implemented later.

---

## 9. Sanity Check Agent (planned)

**Module:** `sanity/sanity_runner.py` (future work)  
**Role:** run fast, deterministic checks before full translation.

### Planned responsibilities

- `run_sanity_checks(config) -> dict`:
  - Use `StringTranslator` on `tests/sanity_check.txt`.
  - Use `JavaTranslator` on `tests/sanity_check.java`.
  - Check for banned tokens and suspicious expansions.
  - Count strings/comments and compare with originals.
  - Return JSON-serializable dict with statuses and metrics.

---

## 10. Quick Function Index (by module)

- `translate_project.py`
  - `parse_args()`
  - `prepare_input()`
  - `iter_project_files()`
  - `build_llm_client()`
  - `main()`

- `core/file_router.py`
  - `is_text_file()`
  - `route_and_process_file()`

- `core/llm_client.py`
  - `BaseLLMClient.translate()`
  - `LlamaCppClient.translate()`
  - `OllamaClient.translate()`

- `core/string_translator.py`
  - `is_human_visible_string()`
  - `StringTranslator.__init__()`
  - `StringTranslator.translate_string()`

- `java_translator.py`
  - `JavaTranslator.__init__()`
  - `JavaTranslator.translate()`

- `core/stats.py`
  - `Stats`
  - `Stats.log_summary()`

- `core/logging_setup.py`
  - `setup_logger()`

- `core/errors.py`
  - `ExceedContextSizeError`

- `sanity/sanity_runner.py` (planned)
  - `run_sanity_checks()`

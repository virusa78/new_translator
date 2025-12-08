# Translation System – Functional Requirements (MVP: Java + Strings)

Language: EN (token-efficient, compact).

## 1. Scope

- Offline, deterministic translation for source projects using local LLM.
- MVP covers:
  - Java files (`.java`): translate comments + string literals only.
  - Simple string translation (used by sanity tests and future APIs).
- Backends:
  - llama.cpp via `/v1/chat/completions`.
  - Ollama via `/api/generate`.

## 2. High-level flow

1. CLI (`translate_project.py`) parses args.
2. Orchestrator:
   - Prepares input dir (unzip if `.zip`).
   - Creates output dir and logger.
   - Builds LLM client, Stats, StringTranslator, JavaTranslator.
   - Enumerates all files under input root (relative paths).
   - For each file, calls File Router.
   - Shows progress (tqdm if TTY).
3. File Router:
   - Decides how to handle file:
     - `.java` → JavaTranslator.
     - Other text / binary → copy as-is (for MVP).
   - Handles all IO, resume logic and error recording.
4. Translators work in memory only:
   - JavaTranslator: text → text, no disk access.
   - StringTranslator: short text → short text, with cache + stats.
5. At the end, Stats summary is logged.

## 3. Translation rules (MVP)

### 3.1 Java files

- Input: full `.java` file text (UTF-8).
- Output: same file structure; only comments and string literals translated.
- Must preserve:
  - Package / import / class / method structure.
  - All code tokens and syntax.
  - Char literals (`'a'`, `'\n'`, etc.).
  - Indentation and line breaks (best effort).
- Translate:
  - Line comments: `// ...`.
  - Block comments: `/* ... */`, `/** ... */`.
  - String literals: `"..."` including multi-line with escapes.
- Use StringTranslator for each comment/string payload.

### 3.2 Strings (sanity, utilities)

- Input: raw string.
- Output: translated string or original if not human-visible.
- Heuristics:
  - Skip obvious keys (no spaces, dot/underscore/dash pattern).
  - Skip path-like tokens (`/`, `\`, no spaces).
- Glossary:
  - Each translated pair is appended to `glossary_suggestions.tsv`.

## 4. Concurrency and progress

- ThreadPoolExecutor used with `--workers` threads.
- Each worker:
  - Logs start/end of file.
  - Delegates work to File Router.
- If stderr is a TTY:
  - tqdm progress bar shows total files and current progress.
- If not a TTY:
  - Only logger output is used (no tqdm).

## 5. Error handling

- All file operations are wrapped in try/except in File Router.
- On error:
  - Increment `error_files`.
  - Log error with full path.
  - Append message into `Stats.errors`.
- LLM errors:
  - Handled inside LLM client; non-200 → RuntimeError.
  - Context overflow → `ExceedContextSizeError` (detected in LLM client).
- `translate_project.py` does not crash on single file failure.

## 6. Resume behavior

- Destination path is computed once per file.
- If destination exists:
  - File is counted as `skipped_files` and is not re-translated.
- For `.java`:
  - Only missing translation outputs are processed.
- For non-text/binary:
  - File is copied once; later runs skip.

## 7. Logging

- Single logger `translator` with:
  - Console handler.
  - File handler: `output/_translation_logs/translation.log`.
- Key messages:
  - Startup configuration (paths, backend, model, workers, langs).
  - Discovered file count.
  - Per file: `[FILE] Start:` / `[FILE] Done:`.
  - LLM calls logged by `core.llm_client` (URL, model, latency).
  - Final Stats summary + errors list.

## 8. Sanity checks (target design, not yet wired for MVP)

- Tests folder: `tests/` with:
  - `sanity_check.txt` – simple string for single-string translation.
  - `sanity_check.java` – representative Java file.
- Sanity runner (future):
  - Calls StringTranslator and JavaTranslator.
  - Checks for banned tokens (e.g. "OpenAI", "API", "Key improvements", "The code now", "Error generating text").
  - Compares sentence and structure ratios.
  - Produces `sanity_report.json` with simple pass/fail and metrics.

## 9. Outputs

- Translated project tree under `--output`.
- Logs under `--output/_translation_logs/`:
  - `translation.log`.
  - `glossary_suggestions.tsv`.
- (Future) `sanity_report.json` and QA artifacts.

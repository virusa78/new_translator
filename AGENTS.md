
# Codebase: Python, .venv   

# Translation Agents (MVP: Java + Strings)

Language: EN (token-efficient)

## 1. Orchestrator CLI Agent

**File:** `translate_project.py`  
**Role:** Top-level coordinator.

**Responsibilities:**
- Parse CLI args (backend, model, langs, paths, workers).
- Init logging, stats, glossary path.
- Init LLM client (`LlamaCppClient` / `OllamaClient`).
- Init shared `StringTranslator`.
- Discover project files (`rglob`).
- For each file:
  - Call File Router Agent.
- At the end:
  - Run Sanity Check Agent.
  - Print summary and sanity status.

**Inputs:**
- CLI arguments.
- File tree under `--input`.

**Outputs:**
- Translated project under `--output`.
- Logs, stats, sanity report.

---

## 2. File Router Agent

**File:** `core/file_pipeline.py` (или внутри `translate_project.py` на MVP)  
**Role:** Map file paths to translation modules; handle IO once.

**Responsibilities:**
- Compute destination path from `src_root`, `dst_root`, `rel_path`.
- RESUME: if destination exists → skip.
- Read source file (UTF-8 text).
- Choose translation module by extension:
  - `.java` → Java Translation Agent.
  - (future) `.html`, `.json`, `.yaml`, `.properties`, generic text.
- Call module as pure text→text function.
- Write translated text to destination.
- Update `Stats` (files, chars, words, llm_time).

**Inputs:**
- `src_root`, `dst_root`, `rel_path`.
- Shared `StringTranslator`.
- Logger, Stats.

**Outputs:**
- Translated file on disk.
- Updated Stats.

---

## 3. LLM Client Agent

**File:** `core/llm_client.py`  
**Classes:** `BaseLLMClient`, `LlamaCppClient`, `OllamaClient`  
**Role:** Uniform LLM transport.

**Responsibilities:**
- `translate(system_prompt, user_prompt) -> (text, dt_seconds)`.
- Add correct payload format:
  - llama.cpp → `/v1/chat/completions` (OpenAI-style).
  - Ollama   → `/api/generate`.
- Handle HTTP errors.
- Detect context overflow and raise `ExceedContextSizeError`.

**Inputs:**
- System prompt (strict rules).
- User prompt per chunk/string.

**Outputs:**
- Raw LLM text.
- Latency for Stats.

---

## 4. String Translator Agent

**File:** `core/string_translator.py`  
**Class:** `StringTranslator`  
**Role:** Safe translation of *single* strings.

**Responsibilities:**
- Maintain in-memory cache `orig → translated`.
- Decide if string is human-visible (`is_human_visible_string`).
- Build user prompt for single string translation.
- Call LLM Client Agent.
- Strip unwanted outer quotes.
- Update Stats (`chars`, `words`, `llm_time`).
- Append pairs to `glossary_suggestions.tsv`.

**Inputs:**
- Raw string.
- System prompt (precomputed per instance).
- LLM Client Agent.

**Outputs:**
- Translated string (or original if not human-visible).

---

## 5. Java Translation Agent

**File:** `java/java_translator.py`  
**Function:** `translate_text(text, string_translator, logger) -> str`  
**Role:** Transform Java source text while preserving syntax.

**Responsibilities:**
- Parse Java source as plain text, single pass.
- Identify and translate only:
  - String literals: `"..."`.
  - Line comments: `// ...`.
  - Block / Javadoc comments: `/* ... */`, `/** ... */`.
- Do **not** translate:
  - Char literals: `'a'`, `'\n'`, etc.
  - Any code outside comments/strings.
- For each zone:
  - Extract inner text.
  - Call String Translator Agent.
  - Reassemble with original delimiters.
- No file IO, no RESUME, no path logic.

**Inputs:**
- Full Java file text.
- `StringTranslator`.
- Logger.

**Outputs:**
- New Java file text, same structure, translated comments/strings.

---

## 6. Sanity Check Agent

**File:** `sanity/sanity_runner.py`  
**Role:** Pre-flight validation before mass translation.

**Responsibilities:**
- `string_simple` test:
  - Read `tests/sanity_check.txt`.
  - Call String Translator Agent.
  - Run checks:
    - Banned tokens: `"OpenAI"`, `"API"`, `"Key improvements"`, `"The code now"`, `"Error generating text"`.
    - Sentence ratio: translated sentences vs original.
- `java_file` test:
  - Read `tests/sanity_check.java`.
  - Use Java Translation Agent + String Translator Agent.
  - Compare:
    - Number of string literals.
    - Number of comments.
    - Simple “skeleton” (code with strings/comments stripped).
    - Banned tokens.
- Produce machine-readable JSON report.

**Inputs:**
- Test files under `tests/`.
- Configured agents (LLM Client, String Translator, Java Translator).

**Outputs:**
- `sanity_report.json` with:
  - status per check (`ok` / `fail`),
  - issues,
  - numeric details.

---

## 7. Stats + Glossary Agent

**File:** `core/stats.py` (или внутри `translate_project.py` на MVP)  
**Role:** Central accounting and term capture.

**Responsibilities:**
- Track:
  - total_files, translated_files, skipped_files, error_files
  - total_input_chars, total_output_chars, total_words
  - llm_time_seconds
  - errors list
- Provide helper for logging final summary.
- Maintain `glossary_suggestions.tsv`:
  - called by String Translator Agent.

**Inputs:**
- Events from File Router, String Translator, Sanity Check.

**Outputs:**
- Stats object for orchestration.
- Glossary file for future manual curation.

---

## 8. QA / Result Map Agent (future)

**File:** `qa/result_map.py` (planned)  
**Role:** Post-processing quality view.

**Responsibilities (future):**
- Aggregate per-file stats and sanity results.
- Build project-level JSON/HTML “translation map”.
- Highlight suspicious files:
  - high sentence expansion,
  - structure mismatches,
  - banned tokens.

**Inputs:**
- Stats.
- Sanity report.
- Per-file metadata.

**Outputs:**
- QA artifacts (JSON/HTML) for human review.

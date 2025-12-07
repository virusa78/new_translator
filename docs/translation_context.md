# Translation System Context (MVP: Java + Strings)

## Goal

Offline translation of source projects using local LLM (llama.cpp / Ollama) with:
- strict code syntax preservation
- translation of human-facing text only
- safety checks against hallucinations and API-like junk

MVP: support
- single-string translation (sanity test)
- Java source files: translate string literals and comments only

## High-Level Flow

1. CLI (`translate_project.py`):
   - parse args (backend, model, langs, paths, workers)
   - init logging, stats, glossary path
   - init LLM client (`LlamaCppClient` or `OllamaClient`)
   - build `StringTranslator` for string-level translation
   - scan project files (`rglob`)
   - for each file call `process_file(rel_path, ...)` in thread pool
   - at end: log stats + summary + sanity check results

2. File pipeline (`translate_project.py` or `core/file_pipeline.py`):
   - decide destination path:
     - default: `dst_root / rel_path`
     - HTML later: `dst_root / rel_path.parent / "en" / rel_path.name`
   - RESUME: if dest exists → skip
   - choose module by extension:
     - `.java` → `java_translator.translate_text(...)`
     - later: `.html`, `.json`, `.yaml`, `.properties`, generic text
   - read source file as UTF-8 text
   - call selected module (pure text→text)
   - write result to destination (UTF-8)
   - update `Stats` (files, chars, words, llm_time)

3. LLM clients (`core/llm_client.py`):
   - `BaseLLMClient`:
     - `translate(system_prompt: str, user_prompt: str) -> tuple[str, float]`
   - `LlamaCppClient`:
     - endpoint: `/v1/chat/completions` (OpenAI-compatible)
     - handles HTTP errors
     - detects context limit errors and raises `ExceedContextSizeError`
   - `OllamaClient`:
     - endpoint: `/api/generate`
     - supports `options` (e.g. `num_ctx`, `temperature`, etc.)

4. String-level translation (`core/string_translator.py`):
   - `class StringTranslator`:
     - fields: `client`, `source_lang`, `target_lang`, `stats`, `cache`, `system_prompt`, `glossary_path`
     - `translate_string(s: str) -> str`:
       - if in cache → return
       - heuristic `is_human_visible_string(s)`:
         - skip i18n-like keys
         - skip bare paths
         - prefer strings with spaces or punctuation
       - build user prompt:
         - strict: “Translate ONLY this string, no comments or explanations”
       - call `client.translate(system_prompt, user_prompt)`
       - update `stats` (chars, words, llm_time)
       - strip outer quotes if модель их добавила
       - cache result
       - append pair to `glossary_suggestions.tsv`
   - system prompt:
     - strict technical translator
     - do not change identifiers, keys, URLs, placeholders, escapes
     - keep backslashes exactly
     - no explanations

5. Java translation module (`java/java_translator.py`):
   - pure function:
     - `translate_text(text: str, string_translator: StringTranslator, logger) -> str`
   - responsibilities:
     - parse Java source linearly
     - preserve all non-text syntax:
       - keywords, identifiers, braces, operators, annotations, etc.
     - detect zones to translate:
       - string literals: `"..."` (Java classic strings)
       - line comments: `// ...`
       - block comments: `/* ... */` and Javadoc `/** ... */`
     - do NOT translate:
       - char literals: `'a'`, `'\n'`, etc.
       - anything outside comments/strings
     - for each zone:
       - pass inner text to `string_translator.translate_string(...)`
       - re-wrap with original delimiters:
         - `"translated"` for strings
         - `// translated` for line comments
         - `/* translated */` for block/Javadoc comments
   - no file IO, no path logic, no RESUME inside module.

6. Sanity check (`sanity/sanity_runner.py`):
   - uses public APIs only:
     - `StringTranslator`
     - `java_translator.translate_text`
   - modes:
     - `string_simple`:
       - read `tests/sanity_check.txt`
       - run through `StringTranslator`
       - check:
         - banned tokens: “OpenAI”, “API”, “Key improvements”, “The code now”, “Error generating text”
         - sentence count ratio (e.g. > 3x → suspicious)
     - `java_file`:
       - read `tests/sanity_check.java`
       - run through `java_translator.translate_text`
       - parse orig vs translated:
         - count string literals
         - count comments
         - compare simple “skeleton hash” (code without strings/comments)
         - check banned tokens
   - outputs JSON report like:
     - status: `ok` / `fail`
     - issues: list of codes + messages
     - details: metrics (length, counts)

7. QA / result map (later):
   - aggregator builds JSON / HTML map of:
     - file-level status
     - sanity results
     - stats per file and per project

1. Краткая выжимка этого чата (что мы сделали / поняли)

Цель проекта (MVP)
Сделать локальную систему перевода исходников поверх твоего llama.cpp/Оllama, сейчас MVP = Java-файлы + одиночные строки, без галлюцинаций и без порчи кода:

Переводятся только комментарии и строковые литералы.

Структура Java-кода, скелет, идентификаторы, сигнатуры методов — должны оставаться 1:1.

Для строк: строгий перевод без объяснений и “Key improvements”.

Есть sanity-check (на примерах), который ловит:

появление запрещённых токенов (OpenAI, API, Key improvements, The code now, Error generating text, и т.п.),

взрыв длины строки,

изменение числа строковых литералов/комментариев и скелета Java.

Рефакторинг монолита → модульная архитектура

Мы разбили старый огромный translate_project.py на логические модули:

translate_project.py — оркестратор CLI.

core/llm_client.py — единый интерфейс к llama.cpp/Ollama.

core/string_translator.py — перевод одной строки + кэш + глоссарий.

core/file_router.py — единственная точка чтения/записи файлов.

core/stats.py — статистика пробега.

core/logging_setup.py — логгер.

java/java_translator.py — модуль для перевода Java-текста (комменты + строки), без IO.

(позже) sanity/ — sanity-чекер и QA.

Ключевые договорённости по дизайну

Только file_router читает/пишет файлы.
Все “переводчики” (JavaTranslator, будущие HtmlTranslator и т.п.) работают по контракту:

translate(text: str) -> str


Никаких путей, файловой системы, Path внутри них.

LLM-клиент один, общая логика:

LlamaCppClient — /v1/chat/completions (OpenAI-совместимый).

OllamaClient — /api/generate.

Оба реализуют интерфейс BaseLLMClient.translate(system_prompt, user_prompt) -> (text, dt_seconds).

ExceedContextSizeError для переполнения контекста.

StringTranslator:

Содержит готовый system-prompt (строгий перевод, без объяснений).

Имеет кэш orig -> translated.

Логика “человеко-видной строки” (is_human_visible_string).

Пишет пары в glossary_suggestions.tsv.

Обновляет статистику (Stats).

JavaTranslator:

Принимает полный текст файла:

Парсит по символам: строковые литералы "...", //, /* */, /** */.

Не трогает char-литералы 'a', '\n', и код вне комментариев/строк.

Для каждой внутренней строки/комментария вызывает StringTranslator.translate.

Собирает результат в текст того же формата.

Никакого общения с файловой системой.

Маршрутизация по типам файлов (пока только Java):

core/file_router.route_and_process_file(...):

Определяет пути src_path, dst_path.

Проверяет RESUME (если dst_path существует — скип).

Если расширение .java — читает текст, делает атомарный перевод:

Для файлов > 10KB — пишет сначала во временный файл, потом rename.

Всё логирует, обновляет Stats.

Конкурентность и прогресс:

Сейчас — параллельность по файлам через ThreadPoolExecutor(max_workers=workers).

tqdm поверх pool.map(worker, files):

Прогрессбар двигается на уровень файлов (1 тик = 1 завершённый файл).

Внутри файлов лог по чанкам/LLM-вызовам ([JAVA], [LLM]).

Позже можно перейти на “1 файл = 1 поток, но чанк-уровень внутри” для лучшего кэша.

Атомарная запись для больших файлов:

Для файлов > 10KB: пишем в dst_path.with_suffix(".tmp"), потом rename → dst_path.

Для мелких можно писать напрямую.

Поддержка sanity-check / QA:

Есть JSON отчёт sanity-чека (пример ты показывал).

План: sanity/sanity_runner.py вызывает:

StringTranslator на tests/sanity_check.txt.

JavaTranslator на tests/sanity_check.java.

Проверки: запрещённые токены, ratio длины, количество строк и комментариев, скелет кода.

8. Progress and Concurrency

Files processed via ThreadPoolExecutor(max_workers=workers).

tqdm progress bar wraps pool.map(worker, files):

Progress unit = 1 finished file.

Inside file:

JavaTranslator chunk-level calls log via [LLM] llama.cpp call… / response….

Later improvements possible:

“1 file = 1 worker, multiple LLM calls inside” (better cache locality).

Per-chunk progress if needed.
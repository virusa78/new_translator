# prompts.py
from __future__ import annotations


def _lang_name(code: str) -> str:
    code = (code or "").lower()
    mapping = {
        "ru": "Russian",
        "en": "English (US)",
        "tr": "Turkish",
        "zh": "Chinese",
    }
    return mapping.get(code, code or "Unknown")


def build_code_system_prompt(source_lang: str, target_lang: str) -> str:
    """
    Строгий системный промт для перевода исходников / технического текста.
    """
    src_name = _lang_name(source_lang)
    tgt_name = _lang_name(target_lang)

    glossary_ru_en = """
TERMINOLOGY (MANDATORY, for Russian → English (US)):
НД → Work Permit (WP)
Наряд-допуск → Work Permit (WP)
Статус → Status
Период действия → Validity Period
Дата согласования → Approval Date
Учетная запись → Account
Пользователь → User
Фильтрация → Filtering
Данные (формы) → Form Data
Данные журнала → Log Data
Событие лога → Log Event
Быстрый старт → Quick Start
Руководство пользователя → User Guide
Настройки → Settings
Сменить пароль → Change Password
Выход → Logout
Внешний ID → External ID
Обновить → Refresh
Удалить → Delete
""".strip()

    body = f"""
You are a STRICT technical translator for SOURCE CODE and technical text
(Java, JSON, configuration files, logs, documentation fragments).

LANGUAGE DIRECTION:
Translate ONLY human-readable text (comments, docstrings, UI strings, user-facing messages):
{src_name} → {tgt_name}

DO NOT TRANSLATE:
- Code identifiers (class, method, variable, enum, constant names).
- Property keys, status codes, internal constants.
- URLs, filenames, file paths, ports, IP addresses.
- Placeholders and formatting tokens:
  %s, %d, %f, %1$s, {{0}}, {{1}}, ${{id}}, ${{user}}, \\n, \\t, \\r, \\\\ and similar.
- Language keywords and syntax.

YOU MUST:
- Preserve code syntax EXACTLY (braces, semicolons, imports, annotations, generics).
- Preserve indentation, line breaks and whitespace.
- Preserve escape sequences exactly (\\n, \\t, \\\", \\\\uXXXX, etc.).
- Translate ONLY the human-facing text inside comments and string literals.
- Do NOT add any explanations, comments, or descriptions of changes.

GLOSSARY (apply strictly when applicable):
{glossary_ru_en}

OUTPUT FORMAT:
Return ONLY the translated content in the same format.
No explanations, no examples, no comments about the code.
""".strip()

    return body


def build_user_prompt_for_string(text: str, source_lang: str, target_lang: str) -> str:
    src_name = _lang_name(source_lang)
    tgt_name = _lang_name(target_lang)
    return (
        f"Translate the following string from {src_name} to {tgt_name}. "
        "Return ONLY the translated string, without quotes, comments or explanations. "
        "Do not add any extra sentences, just a direct translation:\n\n"
        f"{text}"
    )

from __future__ import annotations

import unicodedata


def normalize_text(text: str) -> str:
    """Normalize extracted text for cleaner display/search behavior."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    out: list[str] = []
    for char in normalized:
        if char in {"\n", "\t"}:
            out.append(char)
            continue

        if char.isspace():
            out.append(" ")
            continue

        category = unicodedata.category(char)
        if category in {"Cc", "Cf"}:
            continue

        out.append(char)

    return "".join(out)

from __future__ import annotations

def normalize_text(s: str) -> str:
    """Limpieza ligera: espacios, saltos de línea duplicados, BOM/whitespace raro."""
    if not s:
        return s
    s = s.replace("\ufeff", "")  # BOM
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    while "\n\n\n" in s:
        s = s.replace("\n\n\n", "\n\n")
    return s.strip()
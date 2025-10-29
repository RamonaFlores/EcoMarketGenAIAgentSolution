# src/agent/policy.py
from __future__ import annotations
from typing import List, Dict, Any

def has_policy_evidence(snippets: List[Dict[str, Any]]) -> bool:
    """
    Retorna True si hay al menos un snippet con doc_type 'policy'.
    """
    return any(s.get("doc_type") == "policy" for s in snippets or [])

def summarize_sources(snippets: List[Dict[str, Any]]) -> str:
    """
    Crea una línea de citas comprimida para la respuesta final.
    """
    uniq = {(s.get("doc_type"), s.get("source"), s.get("last_updated")) for s in (snippets or [])}
    if not uniq:
        return "Fuentes: (sin evidencia recuperada)"
    parts = [f"{dt}::{src} (last_updated={lu})" for dt, src, lu in uniq]
    return "Fuentes: " + "; ".join(parts)
# src/loaders/json_loader.py
from __future__ import annotations
import json
from typing import List, Dict, Any
from pathlib import Path
from datetime import date

def load_faqs_json(path: str) -> List[Dict[str, Any]]:
    """
    Carga un archivo JSON con preguntas frecuentes del tipo:
    [
      {"question": "...", "answer": "..."},
      {"question": "...", "answer": "..."}
    ]
    """
    file_path = Path(path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results: List[Dict[str, Any]] = []
    for i, qa in enumerate(data):
        q = qa.get("question", "").strip()
        a = qa.get("answer", "").strip()
        text = f"P: {q}\nR: {a}"
        results.append({
            "text": text,
            "meta": {
                "doc_type": "faq",
                "source": file_path.name,
                "category": "soporte",
                "faq_id": i,
                "last_updated": date.today().isoformat(),
                "language": "es",
            }
        })
    return results
from __future__ import annotations
from typing import List, Dict, Any
from langchain_community.document_loaders import PyPDFLoader
from pathlib import Path
from datetime import date

def load_policy_pdf(path: str) -> List[Dict[str, Any]]:
    """
    Carga un PDF institucional (p. ej. devoluciones.pdf)
    y devuelve una lista de {'text', 'meta'}.
    """
    file_path = Path(path)
    loader = PyPDFLoader(str(file_path))
    docs = loader.load()

    results = []
    for i, d in enumerate(docs):
        results.append({
            "text": d.page_content.strip(),
            "meta": {
                "doc_type": "policy",
                "source": file_path.name,
                "category": "legal",
                "page": i + 1,
                "last_updated": date.today().isoformat(),
                "language": "es",
            }
        })
    return results
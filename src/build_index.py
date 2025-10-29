# src/build_index.py
from __future__ import annotations
import argparse
from typing import List, Dict, Any
from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter

from .config import EMBEDDING_MODEL
from .pinecone_io.upsert import batch_upsert
from .loaders.pdf_loader import load_policy_pdf
from .loaders.csv_loader import load_inventory_csv_or_xlsx
from .loaders.json_loader import load_faqs_json

SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", ".", "!", "?"],
)

def _chunk_docs(raw_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for d in raw_docs:
        parts = SPLITTER.split_text(d["text"])
        for i, part in enumerate(parts):
            meta = dict(d["meta"])
            meta.setdefault("last_updated", Path(d["meta"].get("source","")).stem[:10] or "2025-01-01")
            meta.setdefault("language", "es")
            meta.setdefault("embedding_model", EMBEDDING_MODEL)
            meta["chunk_idx"] = i
            chunks.append({"text": part, "meta": meta})
    return chunks

def main(policy_pdf: str, inventory_file: str, faqs_json: str) -> None:
    print("→ Cargando documentos…")
    docs: List[Dict[str, Any]] = []
    docs += load_policy_pdf(policy_pdf)
    docs += load_inventory_csv_or_xlsx(inventory_file)
    docs += load_faqs_json(faqs_json)

    print(f"→ Total documentos base: {len(docs)}")
    print("→ Chunking recursivo (500/100)…")
    chunks = _chunk_docs(docs)
    print(f"→ Total chunks listos para indexar: {len(chunks)}")

    print("→ Upsert a Pinecone (serverless)…")
    total = batch_upsert(chunks, batch_size=200)
    print(f"✓ Indexación completa: {total} vectores")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construye el índice Pinecone para EcoMarket.")
    parser.add_argument("--policy", required=True, help="Ruta al PDF de políticas (devoluciones.pdf)")
    parser.add_argument("--inventory", required=True, help="Ruta a CSV/XLSX de inventario")
    parser.add_argument("--faqs", required=True, help="Ruta a JSON de FAQs")
    args = parser.parse_args()
    main(args.policy, args.inventory, args.faqs)
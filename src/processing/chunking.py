from __future__ import annotations
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100

def make_chunker(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", "!", "?", ";", ","]
    )

def chunk_documents(
    raw_docs: List[Dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    splitter = make_chunker(chunk_size, chunk_overlap)
    chunks: List[Dict[str, Any]] = []
    for d in raw_docs:
        text = (d.get("text") or "").strip()
        if not text:
            continue
        for i, part in enumerate(splitter.split_text(text)):
            meta = dict(d.get("meta", {}))
            meta["chunk_idx"] = i
            chunks.append({"text": part, "meta": meta})
    return chunks
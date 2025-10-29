from __future__ import annotations
import hashlib
from typing import Iterable, Dict, Any, List
from langchain_openai import OpenAIEmbeddings
from ..config import EMBEDDING_MODEL, VECTOR_NAMESPACE
from .client import get_index

MAX_TEXT_META = 3500  # evita metadatos gigantes (límite ~40KB por item)

def _stable_id(text: str, meta: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    src = f"{meta.get('source','')}|{meta.get('doc_type','')}|{meta.get('chunk_idx','')}|{text}"
    h.update(src.encode("utf-8", errors="ignore"))
    return h.hexdigest()

def _clean_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            cleaned[k] = v
        else:
            cleaned[k] = str(v)
    return cleaned

def embed_texts(texts: List[str]) -> List[List[float]]:
    emb = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return emb.embed_documents(texts)

def batch_upsert(chunks: Iterable[Dict[str, Any]], batch_size: int = 200) -> int:
    index = get_index()
    buffer_texts: List[str] = []
    buffer_metas: List[Dict[str, Any]] = []
    total = 0

    def _flush():
        nonlocal total, buffer_texts, buffer_metas
        if not buffer_texts:
            return

        embeddings = embed_texts(buffer_texts)
        vectors = []
        for text, base_meta, vec in zip(buffer_texts, buffer_metas, embeddings):
            # 1) limpiar metadatos
            meta_clean = _clean_metadata(base_meta)
            # 2) guardar el TEXTO en metadatos (clave crítica para langchain-pinecone)
            meta_clean["text"] = (text[:MAX_TEXT_META]).strip()
            meta_clean["embedding_model"] = EMBEDDING_MODEL

            vid = _stable_id(text, meta_clean)
            # v5: (id, values, metadata)
            vectors.append((vid, vec, meta_clean))

        index.upsert(vectors=vectors, namespace=VECTOR_NAMESPACE)
        total += len(vectors)
        buffer_texts, buffer_metas = [], []

    for ch in chunks:
        buffer_texts.append(ch["text"])
        buffer_metas.append(ch["meta"])
        if len(buffer_texts) >= batch_size:
            _flush()
    _flush()
    return total
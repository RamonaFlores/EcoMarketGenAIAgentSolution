# src/pinecone_io/client.py
from __future__ import annotations
import os
import time
from typing import Optional
from pinecone import Pinecone, ServerlessSpec
from ..config import (
    PINECONE_API_KEY,
    PINECONE_INDEX,
    PINECONE_CLOUD,
    PINECONE_REGION,
    INDEX_DIM,
    INDEX_METRIC,
)

# Singleton del cliente Pinecone (v5)
_pc_singleton: Optional[Pinecone] = None


def get_pc() -> Pinecone:
    """Devuelve un cliente Pinecone singleton (v5)."""
    global _pc_singleton
    if _pc_singleton is None:
        api_key = PINECONE_API_KEY or os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise RuntimeError("Falta PINECONE_API_KEY en .env")
        _pc_singleton = Pinecone(api_key=api_key)
    return _pc_singleton


def _normalize_cloud(value: str) -> str:
    # El SDK espera 'aws' | 'gcp' (minúsculas)
    return (value or "aws").lower()


def ensure_index(name: str = PINECONE_INDEX) -> None:
    """
    Crea el índice serverless si no existe (idempotente) y valida que la
    dimension/métrica coincidan con la configuración del proyecto.
    """
    pc = get_pc()
    cloud = _normalize_cloud(PINECONE_CLOUD)
    region = PINECONE_REGION or "us-east-1"

    existing = {i.name for i in pc.list_indexes()}
    if name not in existing:
        # Crear índice nuevo con la dimensión correcta
        pc.create_index(
            name=name,
            dimension=INDEX_DIM,
            metric=INDEX_METRIC,
            spec=ServerlessSpec(cloud=cloud, region=region),
        )
    else:
        # Validar que el índice existente coincida con la dimensión configurada
        desc = pc.describe_index(name)
        dim = getattr(desc, "dimension", None)
        metric = getattr(desc, "metric", None)
        if dim and dim != INDEX_DIM:
            raise RuntimeError(
                f"Índice '{name}' tiene dimensión {dim}, pero tu proyecto usa {INDEX_DIM}. "
                f"Crea un índice nuevo con dimension={INDEX_DIM} o ajusta el modelo de embeddings."
            )
        if metric and metric != INDEX_METRIC:
            raise RuntimeError(
                f"Índice '{name}' usa métrica '{metric}', pero tu proyecto usa '{INDEX_METRIC}'."
            )

    # Esperar a que el índice esté listo
    for _ in range(60):
        desc = pc.describe_index(name)
        status = getattr(desc, "status", {}) or {}
        if status.get("ready", False):
            return
        time.sleep(1.5)

    # Si llega aquí, no quedó listo en el tiempo esperado (no fatal, pero avisa)
    print(f"⚠️  Aviso: el índice '{name}' podría no estar completamente 'ready' aún.")


def get_index(name: str = PINECONE_INDEX):
    """
    Asegura que el índice exista y devuelve el handler de datos (DataPlane).
    Uso: index.upsert(...), index.query(...), etc.
    """
    ensure_index(name)
    pc = get_pc()
    return pc.Index(name)
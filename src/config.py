# src/config.py
import os
from dotenv import load_dotenv

# --------------------------------------------------------
# 🔧 Carga de variables de entorno
# --------------------------------------------------------
load_dotenv()

# --------------------------------------------------------
# 🔑 OpenAI
# --------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "⚠️ Falta OPENAI_API_KEY en tu .env"

# Modelo principal para generación
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.2))

# Modelo de embeddings (para RAG)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")  # 1536 dims


# --------------------------------------------------------
# 🪣 Pinecone Serverless
# --------------------------------------------------------
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
assert PINECONE_API_KEY, "⚠️ Falta PINECONE_API_KEY en tu .env"

PINECONE_INDEX = os.getenv("PINECONE_INDEX", "masteria22")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# Namespace lógico dentro del índice (permite separar entornos)
VECTOR_NAMESPACE = os.getenv("VECTOR_NAMESPACE", "prod")

# Especificaciones del índice
INDEX_DIM = 1536  # Dimensión del embedding model
INDEX_METRIC = "cosine"


# --------------------------------------------------------
#  Agente y LangGraph
# --------------------------------------------------------
# Checkpoint backend (por ahora en memoria, pero puede ser Redis o SQLite)
CHECKPOINT_BACKEND = os.getenv("CHECKPOINT_BACKEND", "memory")

# Logging y modo debug
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# --------------------------------------------------------
# General
# --------------------------------------------------------
PROJECT_NAME = "EcoMarket RAG-Agent"
DEFAULT_LANGUAGE = "es"

# --------------------------------------------------------
# Mensaje resumen
# --------------------------------------------------------
if DEBUG_MODE:
    print(f"""
    🚀 Configuración cargada para {PROJECT_NAME}
    ├── OpenAI Model: {OPENAI_CHAT_MODEL} ({EMBEDDING_MODEL})
    ├── Pinecone Index: {PINECONE_INDEX} ({VECTOR_NAMESPACE})
    ├── Cloud/Region: {PINECONE_CLOUD}/{PINECONE_REGION}
    └── LangGraph Checkpoint: {CHECKPOINT_BACKEND}
    """)
GEN_MODEL = OPENAI_CHAT_MODEL
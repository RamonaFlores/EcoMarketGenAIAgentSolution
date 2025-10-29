# src/rag/chain.py - VERSIÓN CORREGIDA (bypass LangChain retriever)
from __future__ import annotations
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate
from pinecone import Pinecone
from ..config import (
    GEN_MODEL,
    EMBEDDING_MODEL,
    PINECONE_INDEX,
    VECTOR_NAMESPACE,
    PINECONE_API_KEY,
)
from .prompts import SYSTEM_PROMPT

# -------------------------------------------------------------------
# Prompt de usuario
# -------------------------------------------------------------------
USER_PROMPT = """
Cliente pregunta: {question}

Fragmentos relevantes recuperados:
{context}

Instrucciones:
1) Analiza cuidadosamente los fragmentos.
2) Usa solo la información pertinente para responder.
3) Si hay conflicto, prioriza la fuente más reciente (last_updated).
4) Redacta una respuesta natural, clara y profesional siguiendo el SYSTEM_PROMPT.
5) Cita las fuentes al final (source, doc_type, last_updated).

Responde:
"""

# -------------------------------------------------------------------
# Clase simple para simular Document de LangChain
# -------------------------------------------------------------------
class Document:
    def __init__(self, page_content: str, metadata: Dict[str, Any]):
        self.page_content = page_content
        self.metadata = metadata

# -------------------------------------------------------------------
# Retriever directo usando Pinecone SDK
# -------------------------------------------------------------------
class DirectPineconeRetriever:
    """Retriever que usa Pinecone SDK directamente (bypass LangChain)"""
    
    def __init__(
        self,
        index_name: str,
        namespace: str,
        embedding_model: str,
        k: int = 4,
        metadata_filter: Optional[Dict[str, Any]] = None
    ):
        self.k = k
        self.namespace = namespace
        self.metadata_filter = metadata_filter
        
        # Inicializar embeddings
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # Inicializar Pinecone client
        pc = Pinecone(api_key=PINECONE_API_KEY)
        self.index = pc.Index(index_name)
    
    def get_relevant_documents(self, query: str) -> List[Document]:
        """Recupera documentos relevantes para la query"""
        # Generar embedding de la query
        query_vector = self.embeddings.embed_query(query)
        
        # Buscar en Pinecone
        result = self.index.query(
            vector=query_vector,
            top_k=self.k,
            include_metadata=True,
            namespace=self.namespace,
            filter=self.metadata_filter
        )
        
        # Convertir resultados a Documents
        documents = []
        for match in result.matches:
            # Extraer texto de metadata
            text = match.metadata.get('text', '')
            
            if text:  # Solo incluir si hay texto
                doc = Document(
                    page_content=text,
                    metadata=match.metadata
                )
                documents.append(doc)
        
        return documents

# -------------------------------------------------------------------
# Helper: formatear documentos recuperados
# -------------------------------------------------------------------
def _format_docs(docs: List[Document]) -> str:
    parts = []
    for d in docs:
        src = d.metadata.get("source", "")
        dtype = d.metadata.get("doc_type", "")
        lu = d.metadata.get("last_updated", "")
        snippet = (d.page_content or "").strip().replace("\n", " ")
        parts.append(f"[{dtype} | {src} | last_updated={lu}] {snippet}")
    return "\n".join(parts)

# -------------------------------------------------------------------
# Función principal de respuesta
# -------------------------------------------------------------------
def answer(
    question: str,
    k: int = 4,
    metadata_filter: Optional[Dict[str, Any]] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    Ejecuta el flujo RAG end-to-end usando Pinecone directo.
    Devuelve {"result": <texto>, "source_documents": <list of docs>}.
    """
    # 1. Crear retriever directo
    retriever = DirectPineconeRetriever(
        index_name=PINECONE_INDEX,
        namespace=VECTOR_NAMESPACE,
        embedding_model=EMBEDDING_MODEL,
        k=k,
        metadata_filter=metadata_filter
    )
    
    # 2. Recuperar documentos
    docs = retriever.get_relevant_documents(question)
    
    # 3. Si no hay documentos, retornar mensaje de fallback
    if not docs:
        return {
            "result": (
                "No cuento con información suficiente en la base actual, "
                "puedo escalar tu caso a un agente humano."
            ),
            "source_documents": []
        }
    
    # 4. Formatear contexto
    context = _format_docs(docs)
    
    # 5. Construir prompt completo
    full_prompt = SYSTEM_PROMPT + "\n\n" + USER_PROMPT
    prompt_template = PromptTemplate(
        template=full_prompt,
        input_variables=["question", "context"]
    )
    
    # 6. Generar respuesta con LLM
    llm = ChatOpenAI(model=GEN_MODEL, temperature=temperature)
    
    # Formatear prompt
    formatted_prompt = prompt_template.format(
        question=question,
        context=context
    )
    
    # Invocar LLM
    response = llm.invoke(formatted_prompt)
    
    # 7. Retornar resultado
    return {
        "result": response.content,
        "source_documents": docs
    }

# -------------------------------------------------------------------
# Uso directo (para pruebas rápidas)
# -------------------------------------------------------------------
if __name__ == "__main__":
    q = "¿Puedo devolver un producto si llegó dañado?"
    r = answer(q, k=4, metadata_filter={"doc_type": {"$in": ["policy", "faq"]}})
    print("\nPregunta:", q)
    print("\nRespuesta:\n", r["result"])
    print("\nFuentes:")
    for d in r.get("source_documents", []):
        print(f" - {d.metadata.get('doc_type')} | {d.metadata.get('source')} | {d.metadata.get('last_updated')}")
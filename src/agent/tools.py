
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from typing_extensions import TypedDict
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator
from langchain.tools import tool

# Reutilizamos nuestro RAG para búsqueda de evidencia (no generación)
from ..rag.chain import answer


# =========================
# Tipos de salida (contratos)
# =========================

class RagSnippet(TypedDict, total=False):
    text: str
    source: Optional[str]
    doc_type: Optional[str]
    last_updated: Optional[str]

class RagSearchOutput(TypedDict, total=False):
    snippets: List[RagSnippet]

class GetOrderInfoOutput(TypedDict, total=False):
    found: bool
    reason: Optional[str]
    order: Optional[Dict[str, Any]]

class CheckEligibilityOutput(TypedDict, total=False):
    eligible: bool
    reason: str
    days_elapsed: int
    window_days: int

class GenerateReturnLabelOutput(TypedDict, total=False):
    label_url: str


# =========================
# Tool 1: RAG Search
# =========================
class RagSearchInput(BaseModel):
    """
    Parámetros de entrada para la búsqueda RAG.

    Atributos:
        query: Consulta natural del cliente. Debe ser una pregunta o necesidad concreta.
        k:     Número de fragmentos a recuperar (top-k). Por defecto 6.
        doc_type_filter: Filtro opcional por tipo de documento (p. ej. ["policy", "faq"]).
    """
    query: str = Field(..., description="Consulta del cliente")
    k: int = Field(6, ge=1, le=20, description="Número de fragmentos a recuperar (1..20)")
    doc_type_filter: Optional[List[str]] = Field(None, description="Filtro por doc_type: e.g. ['policy', 'faq']")

    @field_validator("doc_type_filter")
    @classmethod
    def _normalize_doc_types(cls, v):
        if v is None:
            return v
        return [str(x).strip().lower() for x in v if str(x).strip()]



@tool("rag_search", args_schema=RagSearchInput, return_direct=False)
def rag_search(query: str,
    k: int = 6,
    doc_type_filter: Optional[List[str]] = None) -> RagSearchOutput:
    """
    📚 RAG Search — Recupera evidencia antes de decidir.

    Qué hace:
        Interroga la base vectorial de EcoMarket y retorna fragmentos (snippets)
        de documentos relevantes con metadatos. Sirve para sustentar decisiones
        (devoluciones, garantías, plazos) con evidencia verificable.

    Por qué es importante:
        Ancla las respuestas del agente a **fuentes reales** y **versionadas**,
        reduciendo alucinaciones y asegurando trazabilidad (archivo + fecha).

    Entradas (RagSearchInput):
        - query (str): Pregunta del cliente (ej. "¿Puedo devolver si llegó dañado?")
        - k (int):     Top-k de fragmentos (default 6)
        - doc_type_filter (List[str]|None): filtro por tipo (p. ej. ["policy"])

    Salida (RagSearchOutput):
        {
          "snippets": [
            {
              "text": "...",
              "source": "devoluciones.pdf",
              "doc_type": "policy",
              "last_updated": "2025-10-10"
            },
            ...
          ]
        }

    Ejemplo de uso:
        rag_search.invoke({
          "query": "¿Puedo devolver un producto dañado?",
          "k": 6,
          "doc_type_filter": ["policy"]
        })

    Notas:
        - Esta tool NO redacta la respuesta final; sólo devuelve evidencia.
        - Si no hay resultados, retorna {"snippets": []}.
    """
    filt = None
    if doc_type_filter:
        filt = {"doc_type": {"$in": doc_type_filter}}

    res = answer(query, k=k, metadata_filter=filt, temperature=0.0)
    docs = res.get("source_documents", []) or []

    out: RagSearchOutput = {"snippets": []}
    for d in docs:
        out["snippets"].append({
            "text": getattr(d, "page_content", "") or "",
            "source": (d.metadata or {}).get("source"),
            "doc_type": (d.metadata or {}).get("doc_type"),
            "last_updated": (d.metadata or {}).get("last_updated"),
        })
    return out


# =========================
# Tool 2: Order Info (mock)
# =========================

class GetOrderInfoInput(BaseModel):
    """
    Parámetros de entrada para obtener información de una orden.

    Atributos:
        order_id: Identificador de la orden (formato sugerido: EC-####).
    """
    order_id: str = Field(..., description="ID de la orden, p.ej. EC-1001")


# Base mockeada: reemplazable por DB/API real
_FAKE_ORDERS: Dict[str, Dict[str, Any]] = {
    "EC-1001": {
        "order_id": "EC-1001",
        "purchase_date": (datetime.utcnow() - timedelta(days=12)).date().isoformat(),
        "items": [
            {"sku": "ECO-SOAP-500", "category": "higiene"},
            {"sku": "BAMBOO-BRUSH", "category": "higiene"},
        ],
        "customer_email": "cliente@example.com",
        "status": "delivered",
    }
}

@tool("get_order_info", args_schema=GetOrderInfoInput, return_direct=False)
def get_order_info(order_id: str) -> GetOrderInfoOutput:
    """
    📦 Get Order Info — Fuente de verdad transaccional.

    Qué hace:
        Busca la orden del cliente y devuelve sus datos: fecha de compra,
        ítems (SKU + categoría), estado y correo asociado.

    Entradas:
        - order_id (str): Identificador del pedido.

    Salida:
        - Si encuentra: {"found": True, "order": {...}}
        - Si no existe: {"found": False, "reason": "ORDER_NOT_FOUND"}

    Ejemplo:
        get_order_info.invoke({"order_id": "EC-1001"})

    Notas:
        - Implementación mock para la entrega. Sustituible por un conector real (ERP/CMS).
        - Es la **única fuente** para validar SKU en pedido y categoría del producto.
    """
    order = _FAKE_ORDERS.get(order_id)
    if not order:
        return {"found": False, "reason": "ORDER_NOT_FOUND"}
    return {"found": True, "order": order}


# =========================
# Tool 3: Eligibility Check
# =========================

class CheckEligibilityInput(BaseModel):
    """
    Parámetros para verificación de elegibilidad de devolución.

    Atributos:
        purchase_date: ISO date (YYYY-MM-DD) de la compra.
        category:      Categoría del producto (p. ej. 'higiene', 'perecedero').
        condition:     Estado del producto: 'sealed' | 'opened' | 'defective'.
        policy_snippets: Evidencia documental recuperada vía RAG (para trazabilidad).
    """
    purchase_date: str
    category: str
    condition: str = Field(..., description="sealed|opened|defective")
    policy_snippets: List[RagSnippet] = Field(..., description="Snippets de política")

    @field_validator("condition")
    @classmethod
    def _validate_condition(cls, v: str):
        allowed = {"sealed", "opened", "defective"}
        vv = v.strip().lower()
        if vv not in allowed:
            raise ValueError(f"condition debe ser uno de {allowed}")
        return vv


@tool("check_eligibility", args_schema=CheckEligibilityInput, return_direct=False)
def check_eligibility(
    purchase_date: str,
    category: str,
    condition: str,
    policy_snippets: List[RagSnippet],
) -> CheckEligibilityOutput:
    """
    ✅ Eligibility Check — Reglas claras, decisiones auditables.

    Qué hace:
        Evalúa si un producto es elegible para devolución aplicando reglas:
        - Ventana estándar: 30 días desde la compra (inclusive).
        - Exclusión: productos de 'higiene' en estado 'opened' no son retornables.
        - Excepción: 'defective' es elegible (canal de garantía), incluso fuera de ventana.

    Entradas:
        - purchase_date (YYYY-MM-DD)
        - category (str)
        - condition ('sealed' | 'opened' | 'defective')
        - policy_snippets (List[Snippet]) — evidencia para trazabilidad

    Salida (CheckEligibilityOutput):
        {
          "eligible": bool,
          "reason": "WITHIN_WINDOW|WINDOW_EXPIRED|OPENED_HYGIENE_EXCLUDED|DEFECTIVE_EXEMPTION|SKU_NOT_IN_ORDER",
          "days_elapsed": int,
          "window_days": 30
        }

    Ejemplo:
        check_eligibility.invoke({
          "purchase_date": "2025-10-01",
          "category": "higiene",
          "condition": "defective",
          "policy_snippets": [...]
        })
    """
    purchase = datetime.fromisoformat(purchase_date).date()
    days_elapsed = (datetime.utcnow().date() - purchase).days
    window_days = 30

    if condition == "defective":
        return {"eligible": True, "reason": "DEFECTIVE_EXEMPTION", "days_elapsed": days_elapsed, "window_days": window_days}

    if category.strip().lower() == "higiene" and condition == "opened":
        return {"eligible": False, "reason": "OPENED_HYGIENE_EXCLUDED", "days_elapsed": days_elapsed, "window_days": window_days}

    if days_elapsed <= window_days:
        return {"eligible": True, "reason": "WITHIN_WINDOW", "days_elapsed": days_elapsed, "window_days": window_days}
    else:
        return {"eligible": False, "reason": "WINDOW_EXPIRED", "days_elapsed": days_elapsed, "window_days": window_days}


# =========================
# Tool 4: Return Label (idempotente)
# =========================

class GenerateReturnLabelInput(BaseModel):
    """
    Parámetros para generación/recuperación de etiqueta de devolución.

    Atributos:
        order_id:    ID del pedido.
        product_sku: SKU del producto a devolver.
    """
    order_id: str
    product_sku: str


# Almacenamiento en memoria para idempotencia
_LABEL_STORE: Dict[Tuple[str, str], str] = {}


@tool("generate_return_label", args_schema=GenerateReturnLabelInput, return_direct=False)
def generate_return_label(order_id: str, product_sku: str) -> GenerateReturnLabelOutput:
    """
    🏷️ Generate Return Label — Misma entrada, misma etiqueta.

    Qué hace:
        Devuelve una URL de etiqueta de devolución para (order_id, product_sku).
        Es **idempotente**: si la etiqueta ya existe, retorna la misma URL.

    Entradas:
        - order_id (str)
        - product_sku (str)

    Salida:
        { "label_url": "https://labels.ecomarket.local/EC-1001/ECO-SOAP-500" }

    Ejemplo:
        generate_return_label.invoke({
          "order_id": "EC-1001",
          "product_sku": "ECO-SOAP-500"
        })
    """
    key = (order_id, product_sku)
    if key not in _LABEL_STORE:
        _LABEL_STORE[key] = f"https://labels.ecomarket.local/{order_id}/{product_sku}"
    return {"label_url": _LABEL_STORE[key]}
# src/agent/state.py
from __future__ import annotations
from typing import List, Optional
from typing_extensions import TypedDict, NotRequired, Literal


# ---------- Tipos de apoyo (coinciden con lo que devuelven las tools) ----------

class PolicySnippet(TypedDict, total=False):
    text: str
    source: str
    doc_type: str
    last_updated: str


class OrderItem(TypedDict, total=False):
    sku: str
    category: str


class Order(TypedDict, total=False):
    order_id: str
    purchase_date: str  # ISO date (YYYY-MM-DD)
    items: List[OrderItem]
    customer_email: NotRequired[str]
    status: NotRequired[str]


class OrderInfo(TypedDict, total=False):
    found: bool
    reason: NotRequired[str]
    order: NotRequired[Order]


class Eligibility(TypedDict, total=False):
    eligible: bool
    reason: str
    days_elapsed: NotRequired[int]
    window_days: NotRequired[int]


class Slots(TypedDict, total=False):
    order_id: str
    product_sku: str
    # Valor por defecto lo pone el grafo en "sealed" si no viene
    condition: Literal["sealed", "opened", "defective"]


# ---------- Estado del agente (LangGraph) ----------

class AgentState(TypedDict, total=False):
    # Entrada del usuario (texto libre)
    user_msg: str

    # Intent detectado por el nodo INTENT
    intent: Literal["return", "generic"]

    # Slots recolectados (SLOT_FILLING)
    slots: Slots

    # Evidencia de políticas recuperada por RAG (POLICY_RETRIEVE)
    policy_snippets: List[PolicySnippet]

    # Resultado de consulta de orden (ORDER_FETCH)
    order_info: OrderInfo

    # Resultado de elegibilidad (ELIGIBILITY_CHECK)
    eligibility: Eligibility

    # URL de etiqueta si se generó (LABEL_OR_DENY)
    label_url: str

    # Respuesta final redactada por el LLM (ANSWER)
    final_answer: str


__all__ = [
    "PolicySnippet",
    "OrderItem",
    "Order",
    "OrderInfo",
    "Eligibility",
    "Slots",
    "AgentState",
]
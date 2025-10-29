# src/agent/graph.py
from __future__ import annotations
import uuid
from typing import Dict, Any, List
import re
import unicodedata
from difflib import get_close_matches
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate
from ..config import (
    OPENAI_CHAT_MODEL,   # ej: "gpt-4o-mini"
    OPENAI_TEMPERATURE,  # ej: 0.2
)
from ..rag.prompts import SYSTEM_PROMPT
from ..rag.chain import answer as rag_direct_answer  # RAG directo para consultas genéricas
from .state import AgentState
from .tools import rag_search, get_order_info, check_eligibility, generate_return_label
from .policy import has_policy_evidence, summarize_sources


# ------------------------- Helpers -----------------------------------------

RETURN_KEYWORDS = {
    # minúsculas y con/si acentos
    "devolver", "devolucion", "devolución",
    "reembolso", "garantia", "garantía",
    "cambiar", "cambio", "dañado", "daniado", "defectuoso", "rotura"
}

ORDER_REGEX = re.compile(r"\bEC-\d{3,}\b", re.IGNORECASE)
SKU_REGEX   = re.compile(r"\b[A-Z]{2,}-[A-Z0-9\-]{2,}\b")


def _needs_more_slots(slots: Dict[str, Any]) -> List[str]:
    """Devuelve lista de slots faltantes mínimos para evaluar elegibilidad."""
    missing = []
    if not slots.get("order_id"):
        missing.append("order_id")
    if not slots.get("product_sku"):
        missing.append("product_sku")
    return missing


# ------------------------- Nodos -------------------------------------------

def detect_intent(state: AgentState) -> AgentState:
    text = (state.get("user_msg") or "").lower()
    intent = "return" if any(k in text for k in RETURN_KEYWORDS) else "generic"
    state["intent"] = intent
    return state

# Regex más tolerantes (sin \b) y case-insensitive
ORDER_REGEX = re.compile(r"(EC-\d{3,})", re.IGNORECASE)
SKU_REGEX   = re.compile(r"([A-Z]{2,}-[A-Z0-9]+(?:-[A-Z0-9]+)*)", re.IGNORECASE)
DAMAGE_WORDS = {"dañado", "daniado", "defectuoso", "roto", "golpeado", "averiado"}

def _normalize_text(s: str) -> str:
    # 1) Normaliza acentos/compatibilidad Unicode
    s = unicodedata.normalize("NFKC", s)
    # 2) Unifica guiones (reemplaza en/em dash por '-')
    s = s.replace("–", "-").replace("—", "-").replace("−", "-")
    # 3) Espacios raros a espacios normales
    s = s.replace("\u00A0", " ")
    return s

def slot_filling(state: AgentState) -> AgentState:
    slots = state.get("slots") or {}
    raw = state.get("user_msg") or ""
    msg = _normalize_text(raw)

    # order_id
    if "order_id" not in slots:
        m = ORDER_REGEX.search(msg)
        if m:
            slots["order_id"] = m.group(1).upper().rstrip(".,;:!?")  # corta puntuación final

    # product_sku
    if "product_sku" not in slots:
        m = SKU_REGEX.search(msg)
        if m:
            slots["product_sku"] = m.group(1).upper().rstrip(".,;:!?")

    # condition por defecto y auto-marca "defective" si detecta palabras de daño
    msg_lower = msg.lower()
    if "dañado" in msg_lower or "defectuoso" in msg_lower:
        slots["condition"] = "defective"
    elif "abierto" in msg_lower or "lo abrí" in msg_lower or "lo abri" in msg_lower:
        slots["condition"] = "opened"
    else:
        slots.setdefault("condition", "sealed")
    low = msg.lower()
    if any(w in low for w in DAMAGE_WORDS):
        slots["condition"] = "defective"

    state["slots"] = slots
    return state


def policy_retrieve(state: AgentState) -> AgentState:
    # Busca evidencia de políticas para anclar la decisión
    res = rag_search.invoke({"query": state["user_msg"], "k": 6, "doc_type_filter": ["policy"]})
    state["policy_snippets"] = res.get("snippets") or []
    return state


def order_fetch(state: AgentState) -> AgentState:
    oid = (state.get("slots") or {}).get("order_id")
    if not oid:
        return state
    res = get_order_info.invoke({"order_id": oid})
    state["order_info"] = res if res.get("found") else None
    return state


def eligibility_check(state: AgentState) -> AgentState:
    order_info = state.get("order_info") or {}
    order = order_info.get("order") if order_info else None
    if not order:
        return state

    sku = (state.get("slots") or {}).get("product_sku")
    if not sku:
        state["eligibility"] = {"eligible": False, "reason": "MISSING_SKU"}
        return state

    # validar que el sku exista en la orden
    categories = {it["sku"]: it.get("category", "") for it in order.get("items", [])}
    if sku not in categories:
        in_order = list(categories.keys())
        # fuzzy opcional (p.ej. sugiere el más parecido si existe)
        close = get_close_matches(sku, in_order, n=1, cutoff=0.6)
        state["eligibility"] = {
            "eligible": False,
            "reason": "SKU_NOT_IN_ORDER",
            "suggested_skus": in_order,
            "closest_match": close[0] if close else None,
        }
        return state

    res = check_eligibility.invoke({
        "purchase_date": order["purchase_date"],
        "category": categories[sku],
        "condition": (state.get("slots") or {}).get("condition", "sealed"),
        "policy_snippets": state.get("policy_snippets") or []
    })
    state["eligibility"] = res
    return state

def maybe_label_or_deny(state: AgentState) -> AgentState:
    elig = state.get("eligibility") or {}
    if elig.get("eligible"):
        res = generate_return_label.invoke({
            "order_id": (state.get("slots") or {}).get("order_id"),
            "product_sku": (state.get("slots") or {}).get("product_sku"),
        })
        state["label_url"] = res.get("label_url")
    return state


def answer_return(state: AgentState) -> AgentState:
    llm = ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=float(OPENAI_TEMPERATURE))
    snippets = state.get("policy_snippets") or []
    cites = summarize_sources(snippets)
    intent = state.get("intent")
    slots = state.get("slots") or {}
    order = (state.get("order_info") or {}).get("order")
    elig = state.get("eligibility") or {}
    label = state.get("label_url")

    # Detecta caso de SKU_NOT_IN_ORDER para configurar la aclaración
    reason = (elig or {}).get("reason")
    in_order_skus = [it["sku"] for it in (order.get("items", []) if order else [])]
    closest = (elig or {}).get("closest_match")
    missing = []
    if not slots.get("order_id"): missing.append("order_id")
    if not slots.get("product_sku"): missing.append("product_sku")
    need_clarify = bool(missing) or not has_policy_evidence(snippets) or not order or reason == "SKU_NOT_IN_ORDER"

    tmpl = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",
         "Cliente: {user}\n\n"
         "Contexto de políticas (resumen): {cites}\n\n"
         "Intent: {intent}\nSlots: {slots}\nOrder: {order}\nEligibility: {elig}\nLabel: {label}\n"
         "Necesita_aclaracion: {need_clarify}\n"
         "Slots_faltantes: {missing}\n"
         "Sku_en_orden: {in_order_skus}\n"
         "Sugerencia_cercana: {closest}\n\n"
         "Instrucciones:\n"
         "1) Si Necesita_aclaracion es True por 'SKU_NOT_IN_ORDER', NO niegues; pide confirmar el SKU "
         "   mostrando explícitamente las opciones válidas del pedido (Sku_en_orden). "
         "   Si Sugerencia_cercana existe, proponla como opción probable.\n"
         "2) Si luego resulta elegible, da pasos claros y muestra la URL de etiqueta.\n"
         "3) Si no es elegible por políticas (ventana/categoría), explica la razón y ofrece alternativas.\n"
         "4) Cierra con tono empático y profesional, citando brevemente las fuentes (archivo + fecha).")
    ])
    msg = tmpl.format_messages(
        user=state.get("user_msg") or "",
        cites=cites,
        intent=intent,
        slots=slots,
        order=order,
        elig=elig,
        label=label,
        need_clarify=str(need_clarify),
        missing=", ".join(missing) if missing else "—",
        in_order_skus=", ".join(in_order_skus) if in_order_skus else "—",
        closest=closest or "—",
    )
    out = llm.invoke(msg)
    state["final_answer"] = out.content
    return state


def generic_rag_answer(state: AgentState) -> AgentState:
    """
    Para consultas NO relacionadas con devoluciones:
    usa el RAG directo (FAQs + políticas) y retorna respuesta con fuentes.
    """
    res = rag_direct_answer(state.get("user_msg") or "", k=5, metadata_filter=None, temperature=0.0)
    state["final_answer"] = res.get("result") or "No encuentro suficiente información en la base."
    return state


# ------------------------- Grafo -------------------------------------------

def build_graph():
    graph = StateGraph(AgentState)

    # Nodos
    graph.add_node("INTENT", detect_intent)
    graph.add_node("SLOT_FILLING", slot_filling)
    graph.add_node("POLICY_RETRIEVE", policy_retrieve)
    graph.add_node("ORDER_FETCH", order_fetch)
    graph.add_node("ELIGIBILITY_CHECK", eligibility_check)
    graph.add_node("LABEL_OR_DENY", maybe_label_or_deny)
    graph.add_node("ANSWER_RETURN", answer_return)
    graph.add_node("GENERIC_RAG", generic_rag_answer)

    # START → INTENT
    graph.set_entry_point("INTENT")

    # INTENT → (SLOT_FILLING | GENERIC_RAG)
    def route_from_intent(state: AgentState):
        return "SLOT_FILLING" if state.get("intent") == "return" else "GENERIC_RAG"
    graph.add_conditional_edges("INTENT", route_from_intent)

    # SLOT_FILLING → POLICY_RETRIEVE
    graph.add_edge("SLOT_FILLING", "POLICY_RETRIEVE")

    # POLICY_RETRIEVE → (ORDER_FETCH | ANSWER_RETURN)   (si no hay evidencia, responde pidiendo más contexto)
    def route_after_policy(state: AgentState):
        return "ORDER_FETCH" if has_policy_evidence(state.get("policy_snippets")) else "ANSWER_RETURN"
    graph.add_conditional_edges("POLICY_RETRIEVE", route_after_policy)

    # ORDER_FETCH → (ELIGIBILITY_CHECK | ANSWER_RETURN) (si no hay orden, el LLM pide corrección)
    def route_after_order(state: AgentState):
        return "ELIGIBILITY_CHECK" if state.get("order_info") else "ANSWER_RETURN"
    graph.add_conditional_edges("ORDER_FETCH", route_after_order)

    # ELIGIBILITY_CHECK → LABEL_OR_DENY → ANSWER_RETURN → END
    graph.add_edge("ELIGIBILITY_CHECK", "LABEL_OR_DENY")
    graph.add_edge("LABEL_OR_DENY", "ANSWER_RETURN")

    # Cierres
    graph.add_edge("GENERIC_RAG", END)
    graph.add_edge("ANSWER_RETURN", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


def run_agent(user_msg: str, thread_id: str | None = None) -> Dict[str, Any]:
    app = build_graph()
    state: AgentState = {
        "user_msg": user_msg,
        "slots": {},
        "policy_snippets": [],
    }
    # genera uno si no te pasan
    thread_id = thread_id or f"session-{uuid.uuid4()}"
    out = app.invoke(state, config={"configurable": {"thread_id": thread_id}})
    return {
        "answer": out.get("final_answer"),
        "label_url": out.get("label_url"),
        "intent": out.get("intent"),
        "slots": out.get("slots"),
        "thread_id": thread_id,
    }
if __name__ == "__main__":
    print("EcoMarket — Agent demo (Ctrl+C para salir)\n")
    demo_thread = "cli-session-1"  # fijo para conservar contexto en la sesión
    while True:
        try:
            msg = input("> ")
        except KeyboardInterrupt:
            break
        out = run_agent(msg, thread_id=demo_thread)
        print("\n— Intent:", out.get("intent"))
        print("— Slots:", out.get("slots"))
        if out.get("label_url"):
            print("— Label:", out["label_url"])
        print("\nRespuesta:\n", out.get("answer"), "\n")
# src/server/app.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..agent.graph import run_agent
from ..config import PROJECT_NAME

# (Opcional) Gradio UI embebida
try:
    import gradio as gr
    HAVE_GRADIO = True
except Exception:
    HAVE_GRADIO = False

app = FastAPI(title=PROJECT_NAME, version="0.1.0")

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajusta en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Modelos ----------------

class ChatRequest(BaseModel):
    message: str = Field(..., description="Mensaje del usuario")
    thread_id: Optional[str] = Field(None, description="ID lógico de conversación")

class Source(BaseModel):
    doc_type: Optional[str] = None
    source: Optional[str] = None
    last_updated: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    label_url: Optional[str] = None
    intent: Optional[str] = None
    slots: Optional[Dict[str, Any]] = None
    sources: Optional[List[Source]] = None
    thread_id: str

# ---------------- Rutas ----------------

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/v1/agent/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message no puede estar vacío")

    # thread_id opcional (útil para LangGraph checkpointer); si no llega, generamos uno efímero
    thread_id = body.thread_id or f"web-{uuid.uuid4().hex[:8]}"

    # Invocar agente
    result = run_agent(body.message)  # el graph ya incluye checkpoints/flow

    # Fuentes: tomamos del “cita-resumen” que arma el graph (si lo expusiste), o vacío
    # En este ejemplo, extraemos de slots/policy si están presentes (defensivo):
    sources: List[Source] = []
    policy_snippets = result.get("policy_snippets") or []  # por si decides exponerlo luego
    for s in policy_snippets:
        sources.append(Source(doc_type=s.get("doc_type"),
                              source=s.get("source"),
                              last_updated=s.get("last_updated")))

    return ChatResponse(
        answer=result.get("answer", "No se pudo generar respuesta."),
        label_url=result.get("label_url"),
        intent=result.get("intent"),
        slots=result.get("slots"),
        sources=sources or None,
        thread_id=thread_id,
    )

# ---------------- Gradio UI embebida (opcional) ----------------
# Ruta: http://127.0.0.1:8000/ui
if HAVE_GRADIO:
    with gr.Blocks(title=f"{PROJECT_NAME} – Demo") as demo:
        gr.Markdown("## 🌿 EcoMarket – Agente de Devoluciones\nEscribe tu consulta y el agente validará elegibilidad y, si aplica, generará la etiqueta.")
        chat = gr.Chatbot(height=420)
        msg = gr.Textbox(placeholder="Ej: Quiero devolver ECO-SOAP-500, llegó dañado. Pedido EC-1001.")
        clear = gr.Button("Limpiar")

        state_thread = gr.State(value=f"ui-{uuid.uuid4().hex[:8]}")

        def reply(user_msg: str, history: list, thread_id: str):
            if not user_msg.strip():
                return history, thread_id
            # Ejecuta agente en-proceso (sin HTTP extra)
            out = run_agent(user_msg)
            bot = out.get("answer", "No se pudo generar respuesta.")
            # Opcional: añadir la URL de etiqueta si existe
            label = out.get("label_url")
            if label:
                bot += f"\n\n**Etiqueta:** {label}"
            history = (history or []) + [[user_msg, bot]]
            return history, thread_id

        msg.submit(fn=reply, inputs=[msg, chat, state_thread], outputs=[chat, state_thread])
        clear.click(lambda: ([], f"ui-{uuid.uuid4().hex[:8]}"), outputs=[chat, state_thread])

    # Montar en /ui
    from gradio import mount_gradio_app
    app = mount_gradio_app(app, demo, path="/ui")
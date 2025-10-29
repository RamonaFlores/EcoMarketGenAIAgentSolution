# src/server/schemas.py
from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AgentQuery(BaseModel):
    message: str = Field(..., description="Mensaje del usuario en lenguaje natural")
    thread_id: Optional[str] = Field(
        default="demo-thread",
        description="Identificador lógico de conversación (LangGraph checkpoint)"
    )

class AgentResponse(BaseModel):
    answer: str
    label_url: Optional[str] = None
    intent: Optional[str] = None
    slots: Dict[str, Any] = {}
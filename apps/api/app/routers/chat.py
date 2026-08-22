from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.invoice import Invoice
from app.models.user import User
from app.services.audit_service import log_invoice_event
from app.services.chat import answer_query
from app.services.llm import LlmNotConfigured, LlmRequestError, llm_configured

router = APIRouter()


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    scope: Literal["payments", "overview"]
    history: list[ChatTurn] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    scope: Literal["payments", "overview"]


class ChatStatusResponse(BaseModel):
    configured: bool


@router.get("/chat/status", response_model=ChatStatusResponse)
def chat_status(user: User = Depends(get_current_user)):
    return ChatStatusResponse(configured=llm_configured())


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not llm_configured():
        raise HTTPException(
            status_code=503,
            detail="LLM_API_KEY is not set. Add it to apps/api/.env and restart the API.",
        )
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    history = [{"role": t.role, "content": t.content} for t in body.history]
    try:
        reply = await answer_query(
            db, owner_id=user.id, scope=body.scope, message=body.message, history=history
        )
    except LlmNotConfigured:
        raise HTTPException(
            status_code=503,
            detail="LLM_API_KEY is not set. Add it to apps/api/.env and restart the API.",
        )
    except LlmRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    for number in set(re.findall(r"INV-\d+", body.message.upper())):
        row = (
            db.query(Invoice)
            .filter(Invoice.owner_id == user.id, Invoice.invoice_number == number)
            .first()
        )
        if row:
            log_invoice_event(
                db,
                row.id,
                "ai_query",
                "ai",
                event_data={"scope": body.scope, "invoice_number": number},
                evidence={"prompt_snippet": body.message[:200]},
            )

    return ChatResponse(reply=reply, scope=body.scope)

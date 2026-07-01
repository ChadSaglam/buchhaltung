"""AI assistant endpoints — grounded chat + monthly summary over tenant data."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services import ai_assistant

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.get("/status")
async def ai_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Report whether the tenant's Ollama is reachable and which model is used."""
    base_url, model = await ai_assistant.resolve_ollama(user.tenant_id, db)
    import httpx

    try:
        async with httpx.AsyncClient(timeout=6) as client:
            resp = await client.get(f"{base_url}/api/tags")
            ok = resp.status_code == 200
            models = (
                [m.get("name", "") for m in resp.json().get("models", [])] if ok else []
            )
    except Exception:
        ok, models = False, []

    return {"ok": ok, "model": model, "base_url": base_url, "available_models": models}


@router.post("/chat")
async def ai_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream a grounded chat answer as Server-Sent Events."""
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]

    async def event_stream():
        async for frame in ai_assistant.stream_chat(user.tenant_id, db, messages):
            yield frame

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/summary")
async def ai_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a non-streaming monthly summary."""
    return await ai_assistant.summarize(user.tenant_id, db)

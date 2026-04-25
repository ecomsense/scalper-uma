from __future__ import annotations

from pydantic import BaseModel


class SessionStatus(BaseModel):
    connected: bool
    broker: str | None = None
    session_id: str | None = None


class SessionResponse(BaseModel):
    status: str
    message: str
    session: SessionStatus | None = None

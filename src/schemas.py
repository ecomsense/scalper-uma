from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class SessionStatus(BaseModel):
    connected: bool
    broker: Optional[str] = None
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    status: str
    message: str
    session: Optional[SessionStatus] = None

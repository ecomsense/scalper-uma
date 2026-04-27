# Logic State - Shared state between main (controller) and logic app
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.tickrunner import TickRunner
    from src.wserver import Wserver


LOCK_FILE = Path(__file__).parent.parent / 'data' / 'app.pid'


class LogicState:
    def __init__(self) -> None:
        self.running: bool = False
        self.started_at: datetime | None = None
        self.paused: bool = False
        self.pause_until: datetime | None = None
        self.pause_reason: str = ''
        
        # Startup data - preserved across restarts
        self.startup_data: dict[str, Any] | None = None
        
        # App data - runtime state, cleared on stop
        self.app_data: dict[str, Any] | None = None
        
        # Runtime components
        self.ws: Wserver | None = None
        self.runner: TickRunner | None = None
        self.runner_task: Any = None
        
        # Token/symbol state
        self.tokens_nearest: dict[str, str] = {}
        self.quantity: int = 0

    def is_running(self) -> bool:
        return self.running and not self.paused

    def is_paused(self) -> bool:
        if not self.paused:
            return False
        if self.pause_until and datetime.now() > self.pause_until:
            self.paused = False
            self.pause_until = None
            self.pause_reason = ''
            return False
        return True

    def reset(self) -> None:
        self.running = False
        self.started_at = None
        self.paused = False
        self.pause_until = None
        self.pause_reason = ''
        self.app_data = None
        self.ws = None
        self.runner = None
        self.runner_task = None
        self.tokens_nearest = {}
        self.quantity = 0


# Global singleton
_logic_state = LogicState()


def get_logic_state() -> LogicState:
    return _logic_state
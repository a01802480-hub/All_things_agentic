"""
short_memory.py
Manages ephemeral conversation history and active session state (e.g., current plan).
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system", or "tool"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class SessionState:
    session_id: str
    # deque with maxlen acts as an automatic sliding window
    messages: deque = field(default_factory=lambda: deque(maxlen=20))
    active_plan: List[Dict[str, Any]] = field(default_factory=list)
    current_step_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ShortTermMemory:
    """
    In-memory session buffer for handling immediate conversation turns and active tasks.
    Can be replaced or backed with Redis without changing external call signatures.
    """

    def __init__(self, max_history_per_session: int = 20):
        self.max_history = max_history_per_session
        self._sessions: Dict[str, SessionState] = {}

    def _get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(
                session_id=session_id,
                messages=deque(maxlen=self.max_history)
            )
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Appends a single message to the session's sliding window."""
        session = self._get_or_create_session(session_id)
        session.messages.append(ChatMessage(role=role, content=content))

    def get_recent_history(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Retrieves the conversation history formatted for LLM completion calls
        (e.g., [{"role": "user", "content": "..."}]).
        """
        session = self._get_or_create_session(session_id)
        history = [msg.to_dict() for msg in session.messages]
        if limit is not None and limit > 0:
            return history[-limit:]
        return history

    def add_transcript(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Bulk-ingest a chat transcript: [{"role": "user", "content": "..."}, ...]."""
        session = self._get_or_create_session(session_id)
        for message in messages:
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            if content:
                session.messages.append(ChatMessage(role=role, content=content))

    def get_session_ids(self) -> List[str]:
        """All live session ids currently held in short-term memory."""
        return list(self._sessions.keys())

    def update_active_plan(
        self,
        session_id: str,
        plan: List[Dict[str, Any]],
        current_step_id: Optional[str] = None
    ) -> None:
        """Stores the agent's current step-by-step plan for the session."""
        session = self._get_or_create_session(session_id)
        session.active_plan = plan
        if current_step_id:
            session.current_step_id = current_step_id

    def get_active_plan(self, session_id: str) -> Dict[str, Any]:
        """Returns the current plan and active step."""
        session = self._get_or_create_session(session_id)
        return {
            "active_plan": session.active_plan,
            "current_step_id": session.current_step_id
        }

    def clear_session(self, session_id: str) -> None:
        """Wipes a session's history and active state."""
        if session_id in self._sessions:
            del self._sessions[session_id]
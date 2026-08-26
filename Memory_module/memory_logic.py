"""Public orchestration API for the memory module."""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from .long_memory import VectorStore
from .short_memory import ShortTermMemory

load_dotenv()


@dataclass
class MemoryConfig:
    index_name: str = "agent-memory"
    data_dir: str = "Memory_module/data/long_term_memory"
    short_term_window: int = 20
    memory_top_k: int = 3
    memory_min_score: float = 0.2
    use_pinecone: Optional[bool] = None

    @classmethod
    def from_environment(cls) -> "MemoryConfig":
        return cls(index_name=os.getenv("PINECONE_INDEX_NAME", "agent-memory"),
                   data_dir=os.getenv("MEMORY_DATA_DIR", "Memory_module/data/long_term_memory"),
                   short_term_window=int(os.getenv("SHORT_TERM_WINDOW", "20")),
                   memory_top_k=int(os.getenv("MEMORY_TOP_K", "3")),
                   memory_min_score=float(os.getenv("MEMORY_MIN_SCORE", "0.2")))


class MemoryManager:
    def __init__(self, config: Optional[MemoryConfig] = None) -> None:
        self.config = config or MemoryConfig.from_environment()
        self.short_memory = ShortTermMemory(self.config.short_term_window)
        self.long_memory = VectorStore(index_name=self.config.index_name, data_dir=self.config.data_dir,
                                       use_pinecone=self.config.use_pinecone)

    def process_user_input(self, session_id: str, user_id: str, message: str) -> Dict[str, Any]:
        self.short_memory.add_message(session_id, "user", message)
        lowered = message.lower()
        phrases = ("my name is", "i love", "i like", "i prefer", "i work", "i am a")
        if not any(phrase in lowered for phrase in phrases):
            return {"triage_topic": None, "saved_notes": []}
        topic = "name" if "name is" in lowered else "work" if "work" in lowered else "personal"
        note_id = self.save_user_preference(user_id, topic, message)
        return {"triage_topic": topic, "saved_notes": [note_id]}

    def add_assistant_reply(self, session_id: str, content: str) -> None:
        self.short_memory.add_message(session_id, "assistant", content)

    def save_user_preference(self, user_id: str, topic: str, content: str) -> str:
        return self.long_memory.save_note(user_id, topic, content)

    def get_user_profile(self, user_id: str) -> List[Dict[str, Any]]:
        return self.long_memory.local.get_notes(user_id)

    def retrieve_context(self, user_id: str, query: str, top_k: Optional[int] = None) -> str:
        notes = self.long_memory.retrieve_context(user_id, query, top_k or self.config.memory_top_k,
                                                  self.config.memory_min_score)
        return "\n".join(f"- {note.get('topic', 'memory')}: {note.get('content', '')}" for note in notes)

    def build_agent_prompt(self, session_id: str, user_id: str, current_query: str) -> Dict[str, Any]:
        return {"history": self.short_memory.get_recent_history(session_id),
                "long_term_context": self.retrieve_context(user_id, current_query),
                "user_profile": "\n".join(f"- {note['topic']}: {note['content']}"
                                            for note in self.get_user_profile(user_id))}

    def health_check(self) -> Dict[str, Any]:
        return self.long_memory.health_check()

    def delete_note(self, user_id: str, note_id: str) -> None:
        self.long_memory.delete_note(user_id, note_id)

    def delete_user_memory(self, user_id: str) -> None:
        self.long_memory.delete_user_memory(user_id)

    def clear_session(self, session_id: str) -> None:
        self.short_memory.clear_session(session_id)


_manager: Optional[MemoryManager] = None


def get_memory_manager(config: Optional[MemoryConfig] = None) -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager(config)
    return _manager
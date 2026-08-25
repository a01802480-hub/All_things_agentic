"""
memory_logic.py
---------------
The MemoryManager is the ONLY entry point the parent process needs.

It orchestrates:
  * short_memory.ShortTermMemory  - ephemeral conversation window (transcript,
                                     plan state — nothing semantic is kept here)
  * long_memory.VectorStore       - Pinecone vector store (semantic search)
  * long_memory.LocalJsonStore    - compact per-user JSON mirror of long-term facts

The parent process (chatbot, research agent, orchestrator, ...) should import
from this module only:

    from Memory_module import MemoryManager

Data flow (one user turn):

    parent process ──process_user_input(session_id, user_id, message)────┐
         ▲                                                                │
         │                                                short_memory   │ window
         │                                                (transcript)   ▼
         │                                                      triage: is this a
         │                                                      durable fact?
         │                                                             │yes
         │                                            long_memory:     ▼
         │                                            Pinecone upsert + JSON mirror
         │
         └───build_agent_prompt(...)──── long-term context + recent history
"""

import json
import os
import re
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:  # allow configuration through a .env file next to the parent process
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .long_memory import (
    DEFAULT_DATA_DIR,
    DEFAULT_DIMENSION,
    DEFAULT_EMBED_MODEL,
    DEFAULT_INDEX_NAME,
    LocalJsonStore,
    VectorStore,
)
from .short_memory import ShortTermMemory

TRIAGE_LLM_MODEL = "claude-opus-5"


@dataclass
class MemoryConfig:
    """All knobs of the memory subsystem. Prefer MemoryConfig.from_env()."""

    pinecone_api_key: str = ""
    index_name: str = DEFAULT_INDEX_NAME
    # "pinecone" = Pinecone-hosted inference (one key only)
    # "openai"   = bring-your-own embeddings (needs OPENAI_API_KEY)
    embedding_backend: str = "pinecone"
    embed_model: str = DEFAULT_EMBED_MODEL
    dimension: int = DEFAULT_DIMENSION
    cloud: str = "aws"
    region: str = "us-east-1"
    data_dir: str = DEFAULT_DATA_DIR
    short_term_window: int = 20
    top_k: int = 3
    # Minimum cosine similarity to return a note. Model-dependent: ~0.2 for
    # the hosted llama-text-embed-v2, ~0.7 for OpenAI embeddings.
    min_score: float = 0.2
    # Extract facts with an LLM (needs ANTHROPIC_API_KEY) instead of heuristics
    triage_llm: bool = False

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        return cls(
            pinecone_api_key=os.getenv("PINECONE_API_KEY", ""),
            index_name=os.getenv("PINECONE_INDEX_NAME", DEFAULT_INDEX_NAME),
            embedding_backend=os.getenv("EMBEDDING_BACKEND", "pinecone").lower(),
            embed_model=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBED_MODEL),
            dimension=int(os.getenv("EMBEDDING_DIMENSION", DEFAULT_DIMENSION)),
            cloud=os.getenv("PINECONE_CLOUD", "aws"),
            region=os.getenv("PINECONE_REGION", "us-east-1"),
            data_dir=os.getenv("MEMORY_DATA_DIR", DEFAULT_DATA_DIR),
            short_term_window=int(os.getenv("SHORT_TERM_WINDOW", 20)),
            top_k=int(os.getenv("MEMORY_TOP_K", 3)),
            min_score=float(os.getenv("MEMORY_MIN_SCORE", 0.2)),
            triage_llm=os.getenv("TRIAGE_LLM", "false").lower() in ("1", "true", "yes"),
        )


# Heuristic triage: (regex, topic_label). First match wins. Anything that
# doesn't match stays in short-term memory only (it has no durable meaning).
_TRIAGE_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(remember|don'?t forget|never forget|make a note|note that)\b", re.I), "explicit_request"),
    (re.compile(r"\bmy name is\b", re.I), "name"),
    (re.compile(r"\bmy (?:favorite|preferred)\b", re.I), "preference"),
    (re.compile(r"\b(?:i like|i love|i enjoy|i prefer|i(?:'m| am) (?:a )?fan of)\b", re.I), "preference"),
    (re.compile(r"\b(?:i (?:don'?t like|hate|dislike))\b", re.I), "aversion"),
    (re.compile(r"\b(?:i live in|i(?:'m| am) from|my address is)\b", re.I), "location"),
    (re.compile(r"\b(?:i work (?:at|as)|my job is|i(?:'m| am) (?:a|an))\b", re.I), "occupation"),
    (re.compile(r"\bi(?:'m| am) allergic to\b", re.I), "health"),
]


class MemoryManager:
    """High-level memory API used by the parent process.

    Short-term  = the transcript window + plan state (RAM only).
    Long-term   = durable facts (Pinecone vectors + compact JSON mirror).
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig.from_env()
        if not self.config.pinecone_api_key:
            raise ValueError(
                "PINECONE_API_KEY is missing. Set it in the environment or in a .env "
                "file next to the parent process (see .env.example)."
            )
        self.short = ShortTermMemory(max_history_per_session=self.config.short_term_window)
        self.long = VectorStore(
            api_key=self.config.pinecone_api_key,
            index_name=self.config.index_name,
            backend=self.config.embedding_backend,
            embed_model=self.config.embed_model,
            dimension=self.config.dimension,
            cloud=self.config.cloud,
            region=self.config.region,
            json_store=LocalJsonStore(self.config.data_dir),
        )

    # ------------------------------------------------------------------ #
    # Turn pipeline                                                        #
    # ------------------------------------------------------------------ #

    def process_user_input(self, session_id: str, user_id: str, message: str) -> Dict[str, Any]:
        """Feed one incoming user message into memory.

        Always appends the message to the short-term window. If the message
        carries a durable fact (explicit request or heuristic/LLM triage hit),
        it is stored to long-term memory (Pinecone + local JSON).

        Returns a description of what was extracted so the parent can log it:
            {"triage_topic": Optional[str], "saved_notes": [{"note_id", "topic", "content"}]}
        """
        self.short.add_message(session_id, "user", message)
        fact = self._extract_fact(message)
        saved_notes = []
        if fact:
            topic, content = fact
            note_id = self.long.store(user_id, topic, content)
            saved_notes.append({"note_id": note_id, "topic": topic, "content": content})
        return {"triage_topic": fact[0] if fact else None, "saved_notes": saved_notes}

    def build_agent_prompt(self, session_id: str, user_id: str, current_query: str) -> Dict[str, Any]:
        """Assemble everything the parent's LLM needs for this turn.

        Returns:
            {
              "history":           [{"role", "content"}, ...],   # short-term window
              "long_term_context": "formatted retrieved notes",  # semantic hits
              "user_profile":      "formatted full profile",     # from the JSON mirror
            }
        The parent concatenates the two strings into its system prompt.
        """
        history = self.short.get_recent_history(session_id)
        notes = self.long.retrieve(
            user_id, current_query, top_k=self.config.top_k, min_score=self.config.min_score
        )
        profile = self.long.json_store.get_notes(user_id)
        return {
            "history": history,
            "long_term_context": self._format_notes(notes),
            "user_profile": self._format_notes(profile),
        }

    # ------------------------------------------------------------------ #
    # Explicit long-term operations (preferences & important user data)    #
    # ------------------------------------------------------------------ #

    def save_user_preference(self, user_id: str, topic: str, content: str) -> str:
        """Force-save a fact/preference to long-term memory, bypassing triage.

        Returns the note id. This is the method to call for explicit
        'remember this' handling or feedback the parent already validated.
        """
        return self.long.store(user_id, topic, content)

    def get_user_profile(self, user_id: str) -> List[Dict[str, Any]]:
        """All long-term notes for a user, straight from the compact JSON mirror
        (fast, no network round-trip)."""
        return self.long.json_store.get_notes(user_id)

    def retrieve_context(self, user_id: str, query: str, top_k: Optional[int] = None) -> str:
        """Semantic search only: formatted notes relevant to `query`."""
        notes = self.long.retrieve(
            user_id, query, top_k or self.config.top_k, self.config.min_score
        )
        return self._format_notes(notes)

    def delete_note(self, user_id: str, note_id: str) -> None:
        self.long.delete_note(user_id, note_id)

    def delete_user_memory(self, user_id: str) -> None:
        """Wipe all long-term data for a user (Pinecone namespace + JSON file)."""
        self.long.delete_user(user_id)

    # ------------------------------------------------------------------ #
    # Short-term operations (transcript / plan state)                      #
    # ------------------------------------------------------------------ #

    def add_transcript(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Bulk-ingest an existing chat transcript: [{"role", "content"}, ...]."""
        self.short.add_transcript(session_id, messages)

    def add_assistant_reply(self, session_id: str, content: str) -> None:
        self.short.add_message(session_id, "assistant", content)

    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        return self.short.get_recent_history(session_id, limit)

    def set_plan(self, session_id: str, plan: List[Dict[str, Any]], current_step_id: Optional[str] = None) -> None:
        self.short.update_active_plan(session_id, plan, current_step_id)

    def get_plan(self, session_id: str) -> Dict[str, Any]:
        return self.short.get_active_plan(session_id)

    def clear_session(self, session_id: str) -> None:
        self.short.clear_session(session_id)

    def health_check(self) -> Dict[str, Any]:
        """Connectivity report for the parent's /health endpoint."""
        vector_count = None
        try:
            stats = self.long.index.describe_index_stats()
            vector_count = stats.get("total_vector_count")
        except Exception as exc:
            warnings.warn(f"Health check failed: {exc}")
        return {
            "index": self.config.index_name,
            "backend": self.config.embedding_backend,
            "total_vectors": vector_count,
        }

    # ------------------------------------------------------------------ #
    # Triage internals                                                     #
    # ------------------------------------------------------------------ #

    def _extract_fact(self, message: str) -> Optional[Tuple[str, str]]:
        """Decide whether `message` carries a durable fact worth remembering.

        Heuristic regex rules by default; LLM extraction when
        config.triage_llm is enabled (needs ANTHROPIC_API_KEY).
        """
        if self.config.triage_llm:
            fact = self._llm_extract_fact(message)
            if fact:
                return fact
        for pattern, topic in _TRIAGE_RULES:
            if pattern.search(message):
                return (topic, message.strip())
        return None

    def _llm_extract_fact(self, message: str) -> Optional[Tuple[str, str]]:
        try:
            import anthropic  # optional dependency, imported lazily

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
            response = client.beta.messages.create(
                model=TRIAGE_LLM_MODEL,
                max_tokens=1024,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{
                    "role": "user",
                    "content": (
                        "Decide whether this user message contains a durable fact about the user "
                        "worth remembering long-term (name, preference, location, occupation, "
                        "allergy, explicit 'remember' request, ...). Reply with ONLY JSON: "
                        '{"worth_remembering": true|false, "topic": "short label", "content": "the fact"}'
                        f'\n\nMessage: "{message}"'
                    ),
                }],
            )
            text = next((b.text for b in response.content if b.type == "text"), "")
            data = json.loads(text)
            if data.get("worth_remembering") and data.get("content"):
                return (str(data.get("topic") or "general"), str(data["content"]))
        except Exception as exc:
            warnings.warn(f"LLM triage failed, falling back to heuristics: {exc}")
        return None

    @staticmethod
    def _format_notes(notes: List[Dict[str, Any]]) -> str:
        lines = [f"- {n['topic']}: {n['content']}" for n in notes if n.get("content")]
        return "\n".join(lines)


_manager: Optional[MemoryManager] = None


def get_memory_manager(config: Optional[MemoryConfig] = None) -> MemoryManager:
    """Process-wide singleton — the parent process calls this once and reuses it.

    Note: the config is applied on the FIRST call only; later calls return the
    existing instance.
    """
    global _manager
    if _manager is None:
        _manager = MemoryManager(config)
    return _manager

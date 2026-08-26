"""Persistent memory with a Pinecone backend and a local JSON mirror."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class LocalJsonStore:
    """Small, human-readable profile store used for fast reads and tests."""

    def __init__(self, data_dir: str = "Memory_module/data/long_term_memory") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        safe_user_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in user_id)
        return self.data_dir / f"{safe_user_id}.json"

    def get_notes(self, user_id: str) -> List[Dict[str, Any]]:
        path = self._path(user_id)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def save_note(self, user_id: str, note: Dict[str, Any]) -> None:
        notes = [item for item in self.get_notes(user_id) if item["id"] != note["id"]]
        notes.append(note)
        self._path(user_id).write_text(json.dumps(notes, indent=2), encoding="utf-8")

    def delete_note(self, user_id: str, note_id: str) -> None:
        notes = [item for item in self.get_notes(user_id) if item["id"] != note_id]
        path = self._path(user_id)
        if notes:
            path.write_text(json.dumps(notes, indent=2), encoding="utf-8")
        elif path.exists():
            path.unlink()

    def delete_user(self, user_id: str) -> None:
        path = self._path(user_id)
        if path.exists():
            path.unlink()


class VectorStore:
    """Store notes in Pinecone when configured, while mirroring them locally."""

    def __init__(self, index_name: str = "agent-memory", dimension: int = 1536,
                 data_dir: str = "Memory_module/data/long_term_memory",
                 use_pinecone: Optional[bool] = None) -> None:
        self.index_name = index_name
        self.dimension = dimension
        self.local = LocalJsonStore(data_dir)
        self.index = None
        if use_pinecone if use_pinecone is not None else bool(os.getenv("PINECONE_API_KEY")):
            self._connect_pinecone()

    def _connect_pinecone(self) -> None:
        from pinecone import Pinecone, ServerlessSpec

        self.pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        names = [item.name for item in self.pc.list_indexes()]
        if self.index_name in names:
            index_description = self.pc.describe_index(self.index_name)
            self.dimension = int(index_description.dimension)
        else:
            self.pc.create_index(name=self.index_name, dimension=self.dimension, metric="cosine",
                                 spec=ServerlessSpec(cloud=os.getenv("PINECONE_CLOUD", "aws"),
                                                     region=os.getenv("PINECONE_REGION", "us-east-1")))
        self.index = self.pc.Index(self.index_name)

    def _get_embedding(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [(byte / 255.0) * 2.0 - 1.0 for byte in digest]
        return (values * ((self.dimension + len(values) - 1) // len(values)))[:self.dimension]

    def save_note(self, user_id: str, topic: str, content: str) -> str:
        note_id = f"note_{uuid.uuid4().hex[:12]}"
        note = {"id": note_id, "topic": topic, "content": content,
                "saved_at": datetime.now(timezone.utc).isoformat()}
        if self.index is not None:
            self.index.upsert(vectors=[(note_id, self._get_embedding(content), {**note, "source": "memory"})],
                              namespace=user_id)
        self.local.save_note(user_id, note)
        return note_id

    def retrieve_context(self, user_id: str, current_query: str, top_k: int = 3,
                         threshold: float = 0.2) -> List[Dict[str, Any]]:
        if self.index is None:
            return self.local.get_notes(user_id)[-top_k:]
        results = self.index.query(vector=self._get_embedding(current_query), top_k=top_k,
                                   namespace=user_id, include_metadata=True)
        return [{"id": match.id, "score": match.score, **(match.metadata or {})}
                for match in results.matches if match.score >= threshold]

    def delete_note(self, user_id: str, note_id: str) -> None:
        if self.index is not None:
            self.index.delete(ids=[note_id], namespace=user_id)
        self.local.delete_note(user_id, note_id)

    def delete_user_memory(self, user_id: str) -> None:
        if self.index is not None:
            self.index.delete(delete_all=True, namespace=user_id)
        self.local.delete_user(user_id)

    def health_check(self) -> Dict[str, Any]:
        total = self.index.describe_index_stats().total_vector_count if self.index is not None else 0
        return {"index": self.index_name, "backend": "pinecone" if self.index is not None else "local",
                "total_vectors": total}
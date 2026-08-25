"""
long_memory.py
--------------
Persistent semantic memory — the "vector vault".

Two stores, one purpose:

  * VectorStore     – all Pinecone communication. Converts text into vector
                      data (Pinecone-hosted embedding inference by default, or
                      your own OpenAI embeddings) and upserts/queries it.
  * LocalJsonStore  – a compact per-user JSON mirror of every long-term fact.
                      Fast profile reads, offline fallback, minimal footprint.
                      Preferences and important user data live here as plain
                      JSON (whitespace-stripped for size).

Durable facts (preferences, traits, important user data) are written to BOTH
stores by `VectorStore.store()`: Pinecone for semantic search, the JSON file
for the cheap canonical copy.
"""

import json
import os
import uuid
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from pinecone import Pinecone, ServerlessSpec

DEFAULT_INDEX_NAME = "agent-memory"
DEFAULT_EMBED_MODEL = "llama-text-embed-v2"    # Pinecone-hosted inference model
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSION = 1536                        # only used by the "openai" backend
DEFAULT_DATA_DIR = str(Path(__file__).resolve().parent / "data" / "long_term_memory")

# With Pinecone-hosted inference this field is embedded server-side;
# every other field in a record becomes searchable metadata.
_TEXT_FIELD = "chunk_text"


def _val(obj: Any, attr: str, default: Any = None) -> Any:
    """Read `attr` from a dict or an object — Pinecone response shapes differ
    across SDK versions (dicts in v5/v6, dataclass objects in v9+)."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


class LocalJsonStore:
    """Compact per-user JSON mirror of long-term memory.

    Layout:  <data_dir>/<user_id>.json
    Format:  {"notes": [{"id", "topic", "content"}, ...]}
    Written without whitespace to keep the footprint minimal.
    """

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(user_id)) or "user"
        return self.data_dir / f"{safe}.json"

    def _read(self, user_id: str) -> Dict[str, Any]:
        path = self._path(user_id)
        if not path.exists():
            return {"notes": []}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) and "notes" in data else {"notes": []}
        except (json.JSONDecodeError, OSError):
            return {"notes": []}

    def _write(self, user_id: str, data: Dict[str, Any]) -> None:
        with open(self._path(user_id), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))

    def upsert_note(self, user_id: str, note_id: str, topic: str, content: str) -> None:
        data = self._read(user_id)
        for note in data["notes"]:
            if note.get("id") == note_id:
                note["topic"], note["content"] = topic, content
                break
        else:
            data["notes"].append({"id": note_id, "topic": topic, "content": content})
        self._write(user_id, data)

    def remove_note(self, user_id: str, note_id: str) -> None:
        data = self._read(user_id)
        data["notes"] = [n for n in data["notes"] if n.get("id") != note_id]
        self._write(user_id, data)

    def get_notes(self, user_id: str) -> List[Dict[str, Any]]:
        return self._read(user_id).get("notes", [])

    def delete_user(self, user_id: str) -> None:
        path = self._path(user_id)
        if path.exists():
            path.unlink()


class VectorStore:
    """All Pinecone communication lives here and nowhere else.

    Backends:
      * "pinecone" (default) — the index is created with Pinecone's hosted
        inference (create_index_for_model), so embeddings are computed on
        Pinecone's side and only ONE api key is needed.
      * "openai" — bring-your-own embeddings; you embed client-side with the
        OpenAI API and upsert raw vectors (requires OPENAI_API_KEY).
    """

    def __init__(
        self,
        api_key: str,
        index_name: str = DEFAULT_INDEX_NAME,
        backend: str = "pinecone",
        embed_model: str = DEFAULT_EMBED_MODEL,
        dimension: int = DEFAULT_DIMENSION,
        cloud: str = "aws",
        region: str = "us-east-1",
        json_store: Optional[LocalJsonStore] = None,
    ):
        if not api_key:
            raise ValueError("PINECONE_API_KEY is required to build the VectorStore.")
        if backend not in ("pinecone", "openai"):
            raise ValueError(f"Unknown embedding backend '{backend}' (expected 'pinecone' or 'openai').")

        self.backend = backend
        self.embed_model = embed_model
        self.index_name = index_name
        self.json_store = json_store or LocalJsonStore()

        self.pc = Pinecone(api_key=api_key)
        self._ensure_index(dimension, cloud, region)
        self.index = self.pc.Index(index_name)

        self._openai_client = None
        if backend == "openai":
            import openai  # optional dependency, imported lazily
            self._openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # ------------------------------------------------------------ index setup
    def _ensure_index(self, dimension: int, cloud: str, region: str) -> None:
        if self.pc.has_index(self.index_name):
            return
        if self.backend == "pinecone":
            # Pinecone-hosted inference: embeddings are computed server-side,
            # so the index is created "for a model" with a text field map.
            self.pc.create_index_for_model(
                name=self.index_name,
                cloud=cloud,
                region=region,
                embed={"model": self.embed_model, "field_map": {"text": _TEXT_FIELD}},
            )
        else:
            # Bring-your-own embeddings: plain cosine index, we embed client-side.
            self.pc.create_index(
                name=self.index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=cloud, region=region),
            )

    # -------------------------------------------------------------- embeddings
    def _embed(self, text: str) -> List[float]:
        """Client-side embedding — only used by the "openai" backend."""
        if self._openai_client is None:
            raise RuntimeError(
                "OpenAI backend requested but the client is not initialized "
                "(set OPENAI_API_KEY)."
            )
        response = self._openai_client.embeddings.create(model=self.embed_model, input=[text])
        return response.data[0].embedding

    # ------------------------------------------------------------------- store
    def store(self, user_id: str, topic: str, content: str) -> str:
        """Upsert one durable fact. Pinecone + local JSON mirror. Returns the note id."""
        note_id = f"note_{uuid.uuid4().hex[:12]}"
        try:
            if self.backend == "pinecone":
                self.index.upsert_records(
                    namespace=user_id,
                    records=[{"_id": note_id, _TEXT_FIELD: content, "topic": topic, "type": "user_preference"}],
                )
            else:
                self.index.upsert(
                    vectors=[
                        (note_id, self._embed(content),
                         {"topic": topic, "content": content, "type": "user_preference"})
                    ],
                    namespace=user_id,
                )
        except Exception as exc:  # degrade gracefully: the JSON mirror still gets the note
            warnings.warn(f"Pinecone upsert failed ({exc}); saved to local JSON only.")
        self.json_store.upsert_note(user_id, note_id, topic, content)
        return note_id

    def retrieve(
        self, user_id: str, query: str, top_k: int = 3, min_score: float = 0.2
    ) -> List[Dict[str, Any]]:
        """Semantic search over one user's long-term memory.

        min_score is the minimum cosine similarity to return a note. The scale
        depends on the embedding model: llama-text-embed-v2 scores are low
        (0.2 keeps real matches, drops noise), OpenAI embeddings typically run
        higher (0.7 works there).
        """
        try:
            if self.backend == "pinecone":
                result = self.index.search_records(
                    namespace=user_id,
                    query={"inputs": {"text": query}, "top_k": top_k},
                )
                hits = _val(_val(result, "result", result), "hits", []) or []
                notes = []
                for hit in hits:
                    fields = _val(hit, "fields", {}) or {}
                    score = float(_val(hit, "_score", _val(hit, "score", 0.0)) or 0.0)
                    if score < min_score:
                        continue
                    notes.append({
                        "id": _val(hit, "_id", _val(hit, "id", "")) or "",
                        "score": score,
                        "topic": fields.get("topic", "") if isinstance(fields, dict) else "",
                        "content": fields.get(_TEXT_FIELD, "") if isinstance(fields, dict) else "",
                    })
                return notes

            response = self.index.query(
                vector=self._embed(query), top_k=top_k, namespace=user_id, include_metadata=True
            )
            notes = []
            for match in _val(response, "matches", []) or []:
                score = float(_val(match, "score", 0.0) or 0.0)
                if score < min_score:
                    continue
                metadata = _val(match, "metadata", {}) or {}
                notes.append({
                    "id": _val(match, "id", "") or "",
                    "score": score,
                    "topic": metadata.get("topic", "") if isinstance(metadata, dict) else "",
                    "content": metadata.get("content", "") if isinstance(metadata, dict) else "",
                })
            return notes
        except Exception as exc:
            warnings.warn(f"Pinecone query failed ({exc}); no context retrieved.")
            return []

    def delete_note(self, user_id: str, note_id: str) -> None:
        """Remove one note from Pinecone and the JSON mirror."""
        try:
            self.index.delete(ids=[note_id], namespace=user_id)
        except Exception as exc:
            warnings.warn(f"Pinecone delete failed ({exc}); removed from local JSON only.")
        self.json_store.remove_note(user_id, note_id)

    def delete_user(self, user_id: str) -> None:
        """Wipe one user's entire namespace + local JSON file."""
        try:
            self.index.delete(delete_all=True, namespace=user_id)
        except Exception as exc:
            warnings.warn(f"Pinecone namespace wipe failed ({exc}); removed local JSON.")
        self.json_store.delete_user(user_id)

"""
long_memory.py
Handles persistent semantic memory using Pinecone.
Agnostic to the agent calling it; strictly manages embedding, upserting, and retrieval.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from pinecone import Pinecone, ServerlessSpec

class VectorStore:
    def __init__(self, index_name: str = "agent-long-term-memory", dimension: int = 1536):
        """
        Initializes the Pinecone client. 
        Dimension defaults to 1536 (standard for OpenAI text-embedding-3-small).
        """
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable is missing.")

        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        
        self._ensure_index_exists()
        self.index = self.pc.Index(self.index_name)

    def _ensure_index_exists(self) -> None:
        """Creates a serverless index if it does not already exist."""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        if self.index_name not in existing_indexes:
            print(f"Creating new Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1" # Adjust region as needed
                )
            )

    def _get_embedding(self, text: str) -> List[float]:
        """
        Converts raw text into a numerical vector.
        TODO: Replace this mock implementation with your actual embedding provider.
        Example using OpenAI:
            response = openai_client.embeddings.create(input=text, model="text-embedding-3-small")
            return response.data[0].embedding
        """
        # Mock vector for structural testing without burning API credits
        return [0.01] * self.dimension 

    def save_note(self, user_id: str, topic: str, content: str) -> str:
        """
        Embeds and upserts a permanent fact into the user's isolated namespace.
        Returns the generated note ID.
        """
        note_id = f"note_{uuid.uuid4().hex[:12]}"
        vector = self._get_embedding(content)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        metadata = {
            "topic": topic,
            "content": content,
            "saved_at": timestamp,
            "source": "explicit_extraction"
        }
        
        self.index.upsert(
            vectors=[(note_id, vector, metadata)],
            namespace=user_id
        )
        
        return note_id

    def retrieve_context(self, user_id: str, current_query: str, top_k: int = 3, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Retrieves the most semantically relevant notes for a given query.
        Returns a list of metadata dictionaries.
        """
        query_vector = self._get_embedding(current_query)
        
        results = self.index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=user_id,
            include_metadata=True
        )
        
        if not results.matches:
            return []
            
        relevant_notes = []
        for match in results.matches:
            # Filter out low-confidence matches to prevent hallucination noise
            if match.score >= threshold:
                relevant_notes.append({
                    "id": match.id,
                    "score": match.score,
                    "topic": match.metadata.get("topic", "Unknown"),
                    "content": match.metadata.get("content", ""),
                    "saved_at": match.metadata.get("saved_at", "")
                })
                
        return relevant_notes
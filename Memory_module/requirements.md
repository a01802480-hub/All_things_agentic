# Agent Memory Core 🧠

This directory contains the completely decoupled, agnostic memory subsystem for the agent architecture. It provides isolated short-term conversational buffers and long-term persistent semantic storage (Pinecone). 

It is designed as a **Microservice Module**. It has no knowledge of downstream LLMs, prompts, or specific agent logic (e.g., Chatbot vs. Research Agent). It strictly handles data ingestion, state management, and context retrieval.

---

## 1. What It Does

The subsystem is split into three layers:

*   **`short_memory.py`**: Manages volatile, ephemeral state using standard Python structures. It automatically enforces a sliding window (default: 20 messages) to prevent token overflow. State is isolated by `session_id`.
*   **`long_memory.py`**: Handles all vector database operations. It embeds text and upserts it into Pinecone, partitioned by `user_id` (namespace) to guarantee data privacy.
*   **`memory_logic.py`**: The API surface (the `MemoryCore` class). Other modules **only** interact with this file. It orchestrates the reading and writing between short-term and long-term storage.

---

## 2. What It Needs (Dependencies & Setup)

### System Requirements
*   Python 3.8+
*   Single-worker execution for local RAM state: Run FastAPI with `uvicorn main:app --reload` (do not use `--workers` unless backed by Redis).

### Package Dependencies
Ensure these are in your `requirements.txt`:
```txt
pinecone>=6.0
python-dotenv>=1.0
typing-extensions>=4.6
# Your embedding library of choice, e.g., openai or sentence-transformers
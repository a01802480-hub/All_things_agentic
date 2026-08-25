# Memory Module — Requirements (Spec)

What this module must do. Implementation and usage docs: see `README.md`.

## Functional requirements

1. **Independence** — self-contained, importable package; zero imports from,
   and zero shared state with, the chatbot/research/orchestrator processes.
   The parent process only imports `MemoryManager` (via `Memory_module`).

2. **Vector data → Pinecone** — embed text and upsert it to a Pinecone index,
   one namespace per user. Default: Pinecone-hosted inference
   (`llama-text-embed-v2`, single API key). Optional: BYO OpenAI embeddings.

3. **Callable from a higher process** — the parent sends user data and chat
   transcripts in (`process_user_input`, `add_transcript`) and receives memory
   back out (`build_agent_prompt`, `get_user_profile`, `retrieve_context`).

4. **Long-term preferences in Pinecone** — `save_user_preference` persists
   durable facts with semantic retrievability (`retrieve_context`).

5. **Compact local long-term store** — preferences and important user data are
   also mirrored to a minimal-space per-user JSON file
   (`data/long_term_memory/<user_id>.json`, whitespace-stripped). This is the
   fast/offline canonical copy; Pinecone is the search layer over it.

6. **Short-term = everything else** — the transcript window and plan state live
   in RAM only (sliding window, default 20 messages). Messages without durable
   semantic meaning are never persisted.

7. **Triage** — decide automatically whether a message holds a durable fact
   (heuristic rules by default; optional LLM extraction with
   `TRIAGE_LLM=true`).

8. **Docs** — `README.md` covers install, configuration, API reference, and
   integration into a higher intelligence.

## Non-goals

- No user authentication / multi-tenancy enforcement (namespaces + file names
  already isolate users; the parent owns identity).
- No long-term transcript archiving (only durable facts are persisted).
- No replacement for the parent's own LLM loop — this module only feeds it
  context.

## Acceptance checks

- `python -m Memory_module.demo` runs end to end against Pinecone.
- `MemoryManager()` raises a clear error without `PINECONE_API_KEY`.
- Pinecone failure degrades to the JSON mirror (warning, no crash).

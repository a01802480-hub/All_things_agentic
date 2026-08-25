# Memory Module 🧠

An **independent** memory subsystem for higher-level agents (chatbot, research
agent, orchestrator, …). It owns its state, its storage, and its API — the
parent process only ever imports one class: `MemoryManager`.

- **Short-term memory** — the live conversation window + plan state, kept in
  RAM. Everything without durable meaning stays here and is dropped when the
  window rolls over.
- **Long-term memory** — preferences and important user data. Stored in
  **Pinecone** as vector data (semantic search) **and** mirrored to a compact
  per-user **JSON file** (fast profile reads, minimal footprint, offline
  fallback).

---

## 1. Architecture

```text
                ┌────────────────────────────────────────────┐
                │            PARENT PROCESS                  │
                │  (chatbot / research agent / orchestrator) │
                └───────────────┬────────────────────────────┘
                                │  one import, six calls
                                ▼
                  ┌──────────────────────────────┐
                  │       MemoryManager          │   <- public API (this file)
                  │       memory_logic.py        │
                  └──────┬───────────────┬───────┘
                         │               │
         ┌───────────────▼───────┐   ┌───▼────────────────────┐
         │   ShortTermMemory     │   │      VectorStore       │
         │   short_memory.py     │   │      long_memory.py    │
         │   ───────────────     │   │   ─────────────────    │
         │  transcript window    │   │  Pinecone index        │
         │  active plan state    │   │  (upsert / semantic    │
         │  (RAM only, sliding)  │   │   search per user)     │
         └───────────────────────┘   │  + LocalJsonStore      │
                                     │    data/long_term_     │
                                     │    memory/<user>.json  │
                                     └────────────────────────┘
```

| File | Role |
|---|---|
| `memory_logic.py` | `MemoryManager` — the only import the parent process needs. Triage pipeline, context assembly, config, singleton accessor. |
| `short_memory.py` | `ShortTermMemory` — in-memory sliding window of messages + plan state per session. |
| `long_memory.py` | `VectorStore` (all Pinecone communication) + `LocalJsonStore` (compact JSON mirror). |
| `demo.py` | Runnable end-to-end demo. |
| `requirements.txt` | pip dependencies. |
| `.env.example` | Environment variable template. |

The module is self-contained: it imports nothing from chatbot/research code,
shares no global state with them (the only optional singleton is its own), and
writes only to its own data directory.

---

## 2. Installation

```bash
pip install -r Memory_module/requirements.txt
```

Recommended:

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r Memory_module/requirements.txt
```

Requires Python 3.10+.

---

## 3. Configuration

Copy `.env.example` to `.env` (project root) and fill in. **`PINECONE_API_KEY`
is the only required value** when using the default backend.

| Variable | Default | Purpose |
|---|---|---|
| `PINECONE_API_KEY` | — (**required**) | Pinecone API key (`pcsk_...`). |
| `PINECONE_INDEX_NAME` | `agent-memory` | Vector index name. Created automatically if missing. |
| `EMBEDDING_BACKEND` | `pinecone` | `pinecone` = Pinecone-hosted embeddings (one key, recommended). `openai` = bring-your-own embeddings. |
| `EMBEDDING_MODEL` | `llama-text-embed-v2` | Hosted inference model (`pinecone` backend) or OpenAI embedding model (`openai` backend, e.g. `text-embedding-3-small`). |
| `EMBEDDING_DIMENSION` | `1536` | Only used by the `openai` backend. |
| `PINECONE_CLOUD` / `PINECONE_REGION` | `aws` / `us-east-1` | Where the index is created (first run only). |
| `MEMORY_DATA_DIR` | `Memory_module/data/long_term_memory` | Where the per-user JSON mirrors live. |
| `SHORT_TERM_WINDOW` | `20` | Messages kept per session in short-term memory. |
| `MEMORY_TOP_K` | `3` | Notes retrieved per semantic search. |
| `MEMORY_MIN_SCORE` | `0.2` | Minimum cosine similarity to return a note. Model-dependent: ~`0.2` for the hosted `llama-text-embed-v2`, ~`0.7` for OpenAI embeddings. |
| `TRIAGE_LLM` | `false` | `true` = extract facts with an LLM (`claude-opus-5`, needs `ANTHROPIC_API_KEY`) instead of the built-in rules. |
| `OPENAI_API_KEY` | — | Only needed with `EMBEDDING_BACKEND=openai`. |

`.env` is loaded automatically at import time (python-dotenv), so the parent
process can also just set these as real environment variables.

---

## 4. Quick start

```bash
python -m Memory_module.demo
```

From the repository root. First run creates the Pinecone index (~1 minute),
then it saves two preferences, runs one triaged turn, and prints the profile +
retrieved context.

Minimal code:

```python
from Memory_module import MemoryManager

memory = MemoryManager()  # config from .env / environment

memory.save_user_preference("user_42", "food", "Vegetarian, allergic to peanuts")
print(memory.build_agent_prompt("session_1", "user_42", "Suggest a dinner recipe"))
```

---

## 5. Public API reference

The parent process talks to the module exclusively through `MemoryManager`.

### Turn pipeline

| Method | What it does |
|---|---|
| `process_user_input(session_id, user_id, message) -> dict` | Appends the message to the short-term window, runs the **triage** (is this a durable fact?), and stores it to long-term memory if so. Returns `{"triage_topic", "saved_notes"}`. |
| `build_agent_prompt(session_id, user_id, current_query) -> dict` | Assembles everything the parent's LLM needs: `{"history": [...], "long_term_context": "...", "user_profile": "..."}`. Concatenate the two strings into your system prompt. |
| `add_assistant_reply(session_id, content)` | Appends the agent's reply to the transcript window. |

### Long-term (preferences & important user data)

| Method | What it does |
|---|---|
| `save_user_preference(user_id, topic, content) -> note_id` | Force-save a fact, **bypassing triage**. Use for explicit "remember this" commands or validated feedback. Writes Pinecone + JSON mirror. |
| `get_user_profile(user_id) -> list[dict]` | All long-term notes for a user from the JSON mirror — fast, no network call. |
| `retrieve_context(user_id, query, top_k=None) -> str` | Semantic search only; returns formatted notes relevant to `query`. |
| `delete_note(user_id, note_id)` | Removes one note from Pinecone and the JSON mirror. |
| `delete_user_memory(user_id)` | Wipes a user's entire Pinecone namespace + JSON file. |

### Short-term (transcript & plan state)

| Method | What it does |
|---|---|
| `add_transcript(session_id, messages)` | Bulk-ingest an existing chat transcript: `[{"role": "user", "content": "..."}, ...]`. |
| `get_history(session_id, limit=None) -> list[dict]` | The recent window, ready for an LLM `messages` list. |
| `set_plan(session_id, plan, current_step_id=None)` / `get_plan(session_id)` | Track the agent's active step-by-step plan. |
| `clear_session(session_id)` | Wipe a session's window and plan state. |

### Utilities

| Method | What it does |
|---|---|
| `health_check() -> dict` | `{"index", "backend", "total_vectors"}` for a `/health` endpoint. |
| `get_memory_manager(config=None)` | Process-wide singleton; config applies on the first call only. |

---

## 6. Implementing the module into a higher intelligence

The pattern for every parent process is the same three calls per turn:
**ingest → assemble → reply back**.

### 6.1 Chatbot (FastAPI-style)

```python
from fastapi import FastAPI
from Memory_module import get_memory_manager

app = FastAPI()
memory = get_memory_manager()

@app.post("/chat")
async def chat(payload: ChatRequest):  # {session_id, user_id, message}
    # 1) Ingest the user turn; triage extracts durable facts automatically
    memory.process_user_input(payload.session_id, payload.user_id, payload.message)

    # 2) Assemble the context for the LLM call
    ctx = memory.build_agent_prompt(payload.session_id, payload.user_id, payload.message)
    system_prompt = (
        "You are the assistant.\n"
        f"Facts the user has shared:\n{ctx['user_profile']}\n"
        f"Relevant memories:\n{ctx['long_term_context']}"
    )

    # 3) Call your LLM with ctx["history"] as the messages list
    reply = call_your_llm(system_prompt, ctx["history"])

    # 4) Put the reply back into the transcript window
    memory.add_assistant_reply(payload.session_id, reply)
    return {"reply": reply}
```

### 6.2 Research agent (reactive loop)

```python
from Memory_module import MemoryManager

memory = MemoryManager()

# Seed a session from a previous run
memory.add_transcript("research_run_17", load_old_transcript())

# Explicit long-term saves the agent decides to make
memory.save_user_preference(user_id, "research_goal", "Building a RAG pipeline benchmark")

# Each step of the loop:
for step in plan.steps:
    ctx = memory.build_agent_prompt("research_run_17", user_id, step.query)
    step_output = run_llm_step(ctx["history"], ctx["long_term_context"])
    memory.add_assistant_reply("research_run_17", step_output)

# Hand the profile over at the end of the run
report_intro = memory.get_user_profile(user_id)
```

### 6.3 Calling conventions

- **Send the transcript in** → `process_user_input` (per message) or
  `add_transcript` (bulk, e.g. restoring a session).
- **Get long-term preferences back** → `get_user_profile` (full profile) or
  `retrieve_context` (semantic matches for the current query).
- **Force-remember something** → `save_user_preference`.
- **Feed the LLM** → `build_agent_prompt` returns the exact pieces to splice
  into your prompt.

### 6.4 Threading / multi-process notes

- One `MemoryManager` per process; `get_memory_manager()` gives a singleton.
- The JSON mirror is **last-write-wins** per user file — if several processes
  write to the same `user_id` concurrently, one should own writes for that
  user. Pinecone itself handles concurrent upserts fine.
- Short-term memory is per-process RAM by design; restart = new window.

---

## 7. How memory is stored

### 7.1 Pinecone (vector data)

One index, one **namespace per `user_id`**. Each note is one record:

- `pinecone` backend (default): text in `chunk_text` is embedded server-side
  by `llama-text-embed-v2`; `topic` and `type` become metadata. Search uses
  `search_records` with the same hosted model — only the Pinecone key needed.
- `openai` backend: you embed client-side (`text-embedding-3-small`, 1536-d)
  and upsert raw vectors into a cosine index.

If the index doesn't exist, it is created on first init (`create_index_for_model`
for the hosted backend). Embedding backend and model are fixed per index —
pick them before first run, or delete the index to switch.

### 7.2 Local JSON mirror (compact long-term store)

```
Memory_module/data/long_term_memory/<user_id>.json
```

```json
{"notes":[{"id":"note_ab12cd34ef56","topic":"food","content":"Loves Italian food, especially homemade pasta"}]}
```

- Whitespace-stripped JSON — smallest practical footprint.
- Written on every save, so `get_user_profile` needs no network call and the
  data survives a Pinecone outage.
- This is the canonical copy of *what this module wrote*; Pinecone is the
  semantic search layer over the same notes.

### 7.3 Short-term (RAM)

A `deque` window of the last N messages per session + the active plan. Nothing
is written to disk. Messages that don't match any triage rule simply roll out
of the window — that is by design ("everything without semantic meaning").

### 7.4 Triage rules

A message is stored long-term when it matches (first match wins):

| Pattern | Topic label |
|---|---|
| "remember / don't forget / note that ..." | `explicit_request` |
| "my name is ..." | `name` |
| "my favorite / preferred ..." | `preference` |
| "I like / love / enjoy / prefer ..." | `preference` |
| "I don't like / hate / dislike ..." | `aversion` |
| "I live in / I'm from / my address is ..." | `location` |
| "I work at / as / my job is ..." | `occupation` |
| "I'm allergic to ..." | `health` |

Set `TRIAGE_LLM=true` (+ `ANTHROPIC_API_KEY`) to replace the rules with an LLM
call that extracts `{worth_remembering, topic, content}` and falls back to the
rules on any failure. Extend the rules by editing `_TRIAGE_RULES` in
`memory_logic.py`.

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ValueError: PINECONE_API_KEY is missing` | Set it in `.env` or the environment. |
| 401 / invalid key | The key was rotated or mistyped — check the Pinecone console. |
| Index creation error | The index name/backend/model combination is fixed at creation; delete the old index to switch backend or model, or use a new `PINECONE_INDEX_NAME`. |
| `search_records` errors | The index was not created with hosted inference. Recreate it with `EMBEDDING_BACKEND=pinecone` or switch to `openai`. |
| OpenAI backend dimension mismatch | `EMBEDDING_DIMENSION` must match your embedding model (1536 for `text-embedding-3-small`/`ada-002`, 3072 for `3-large`). |
| `RuntimeError: OpenAI backend ... not initialized` | `OPENAI_API_KEY` not set. |
| Pinecone warnings ("saved to local JSON only") | Network/API failure — the JSON mirror still has the data; writes resume when Pinecone is back. |
| "LLM triage failed, falling back to heuristics" | Optional path only; missing `ANTHROPIC_API_KEY`/`anthropic` package or API error. Heuristics still ran. |

---

## 9. Security notes

- **Never commit API keys.** `.env` is gitignored; use `.env.example` for
  documentation.
- ⚠️ **The Pinecone key previously hardcoded in `long_memory.py` is in git
  history (commit `0bae63e`).** Rotate it in the Pinecone console and update
  `.env`.
- `delete_user_memory` / `delete_note` are destructive — call them only on
  explicit user requests (GDPR-style deletion).

---

## 10. File index

```
Memory_module/
├── README.md            # this file
├── requirements.md      # functional requirements / spec
├── requirements.txt     # pip dependencies
├── __init__.py          # package exports
├── memory_logic.py      # MemoryManager (public API) + triage + config
├── long_memory.py       # VectorStore (Pinecone) + LocalJsonStore (JSON mirror)
├── short_memory.py      # ShortTermMemory (transcript window + plan state)
└── demo.py              # runnable end-to-end demo
```

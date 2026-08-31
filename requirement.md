# All Things Agentic — Requirements & Run Guide

Everything you need to install, configure, and run the **All Things Agentic** multi-agent
framework. The master entry point is **`main.py`** at the repository root.

---

## 1. Project Overview

The system is a **modular multi-agent orchestrator**. You talk to it from the terminal,
an **Architect** agent (powered by the Gemini API) breaks your request into a task graph,
and it dispatches each task to independent worker modules that are discovered automatically
at boot time.

```
main.py
   │  terminal input
   ▼
ChatAnalyzer  (The architect/chat_to_architect.py)      — intercepts user chat, adds urgency/constraints
   ▼
Architect     (The architect/Architect_logic.py)        — Gemini-powered planner + orchestrator
   │  1. scans every *_module/ folder, registers workers with an `execute` function
   │  2. asks Gemini (gemini-3.6-flash) for a JSON task plan
   │  3. shows you the plan (Human-in-the-Loop — approve, modify, or cancel)
   │  4. runs the tasks in parallel, respecting dependencies
   ▼
Workers:  writing_module → clarity_module → research_module (researchmodu) → programing_module
   │
   ▼
outputs/  — WriterAgent saves its synthesized reports here (.txt / .tex)
```

| Piece | Path | Role |
|---|---|---|
| Master entry | `main.py` | Boots the system, runs the interactive loop |
| Front door | `The architect/chat_to_architect.py` | `ChatAnalyzer` — chat → intent → Architect |
| Orchestrator | `The architect/Architect_logic.py` | `Architect` — Gemini planning, DAG execution, HITL |
| Research | `research_module/researchmodu.py` | Live web search (DuckDuckGo) + Gemini trust-judging |
| Writing | `writing_module/writing_module.py` | Synthesizes academic LaTeX reports into `outputs/` |
| Clarity | `clarity_module/clairty_module.py` | Rewrites raw data for readability and flow |
| Programming | `programing_module/programing_module.py` | Placeholder — **currently empty, does not register** |
| Memory | `Memory_module/` | Pinecone-backed short/long-term memory (standalone API) |
| Chat app | `chat_module/` | Git submodule — standalone Groq/Gemini chat app |
| Tests | `tests/` | `unittest` suite for the Memory module |

---

## 2. System Requirements

| Requirement | Minimum | Notes |
|---|---|---|
| OS | Windows 10/11 (also works on macOS/Linux) | Repo is optimized for Windows PowerShell |
| Python | **3.9+** (3.14.3 verified in use) | `python --version` to check |
| Git | Any recent version | Needed for the repo and its **two submodules** |
| Internet | Required | Gemini API, Pinecone, and web-search calls are remote |
| Gemini API key | Required for `main.py` | The Architect refuses to boot without it |
| Pinecone account | Only for the Memory module | Optional if you never use memory features |

---

## 3. Environment Variables (`.env`)

Create a `.env` file in the **repository root** (copy from `.env.example`).
`.env` is gitignored — never commit real keys.

| Variable | Required? | Used by | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes (master run)** | Architect, writer, clarity, research, chat module | Google Gemini API key |
| `SEARCH_API_KEY` | Only for `research.py` standalone | `research_module/research.py` | LangSearch API key (model `brave`) |
| `PINECONE_API_KEY` | Only for memory features | Memory module | Pinecone API key |
| `PINECONE_INDEX_NAME` | Memory (default `agent-memory`) | Memory module | Index name |
| `PINECONE_CLOUD` | Memory (default `aws`) | Memory module | Cloud provider |
| `PINECONE_REGION` | Memory (default `us-east-1`) | Memory module | Region |
| `EMBEDDING_BACKEND` | Memory (default `pinecone`) | Memory module | `pinecone` or `openai` embedding backend |
| `EMBEDDING_MODEL` | Memory (default `llama-text-embed-v2`) | Memory module | Embedding model name |
| `SHORT_TERM_WINDOW` | Optional | Memory module | Short-term conversation window size |
| `MEMORY_TOP_K` | Optional | Memory module | Notes retrieved per query |
| `MEMORY_MIN_SCORE` | Optional | Memory module | Minimum similarity score (0.2 for llama, ~0.7 for OpenAI) |
| `TRIAGE_LLM` | Optional | Memory module | `true` = extract facts with an LLM (needs `anthropic` package) |

Example minimal `.env` for the master run:

```text
GEMINI_API_KEY=your_gemini_key_here
```

Full example (memory + search included):

```text
GEMINI_API_KEY=your_gemini_key_here
SEARCH_API_KEY=your_langsearch_key_here
PINECONE_API_KEY=pcsk_your_pinecone_key_here
PINECONE_INDEX_NAME=agent-memory
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
EMBEDDING_BACKEND=pinecone
EMBEDDING_MODEL=llama-text-embed-v2
SHORT_TERM_WINDOW=20
MEMORY_TOP_K=3
MEMORY_MIN_SCORE=0.2
TRIAGE_LLM=false
```

---

## 4. Python Dependencies

All dependencies are consolidated in **`requirements.txt`** at the repository root.
Install everything in one shot:

```powershell
pip install -r requirements.txt
```

### What each package is for

| Package | Needed for |
|---|---|
| `google-genai` | Gemini SDK — Architect, Writer, Clarity, and Research agents (**core**) |
| `python-dotenv` | `.env` loading in all modules (**core**) |
| `pydantic` | Architect task/state models (**core**) |
| `ddgs` | Live DuckDuckGo search in `researchmodu.py` (falls back gracefully if missing) |
| `pinecone>=6.0` | Memory module (Pinecone long-term memory) |
| `typing-extensions` | Required by the Pinecone SDK |
| `groq` | Standalone chat app in `chat_module` (git submodule) |
| `openai` *(commented out)* | **Only** the standalone `research.py` demo script (LangSearch). ⚠️ See Troubleshooting #3 before installing it |
| `anthropic` *(commented out)* | Optional LLM triage in the Memory module (`TRIAGE_LLM=true`) |

The two optional packages are intentionally commented out in `requirements.txt`:
`openai` can block the master run at boot (see Troubleshooting #3), and `anthropic`
is only needed with `TRIAGE_LLM=true`. Uncomment them only if you use those features.

Module-level requirement files also exist inside `Memory_module/requirements.txt`
and `chat_module/requirements.txt` if you run those modules standalone.

---

## 5. Installation (Windows / PowerShell)

### 5.1 Clone the repository **with submodules**

The `research_module` and `chat_module` folders are **git submodules** — they will be
empty unless you clone recursively:

```powershell
git clone --recurse-submodules https://github.com/a01802480-hub/All_things_agentic.git
cd All_things_agentic
```

If you already cloned without submodules:

```powershell
git submodule update --init --recursive
```

### 5.2 Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation scripts:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 5.3 Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5.4 Configure your API key

```powershell
Copy-Item .env.example .env
notepad .env
```

Put your real `GEMINI_API_KEY` in `.env`, then verify it loads (without printing it):

```powershell
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Gemini key loaded:', bool(os.getenv('GEMINI_API_KEY')))"
```

The result must be `Gemini key loaded: True`.

---

## 6. Running the Project (Master Run)

From the repository root, with the virtual environment active:

```powershell
python main.py
```

You should see the boot banner, then the interactive prompt:

```text
 ALL THINGS AGENTIC - ARCHITECT TERMINAL BOOTING
 ...
[USER_12345] >>
```

### Interaction flow

1. **Type a request**, e.g.
   `Research quantum error correction and write a full report on it.`
2. The **Architect shows a proposed plan** — a numbered list of tasks and which
   worker module will execute each.
3. **Human-in-the-Loop prompt** — you must confirm the plan:
   - Press `[ENTER]` → approve and execute
   - Type instructions (e.g. `Make it more mathematical`, `Add a synthesis step`) → the
     Architect re-plans with your feedback
   - Type `cancel` → abort the workflow
4. Tasks run (in parallel where dependencies allow) and each result is printed.
5. Writer tasks save their reports to the **`outputs/`** folder (LaTeX `.tex` files).

### Exit / quit

- Type `exit` or `quit` at the main prompt
- `Ctrl+C` force-quits gracefully

### Notes

- `main.py` sets the Windows selector event-loop policy automatically — no extra flags
  are needed on Windows.
- The user ID is hardcoded as `USER_12345` for the demo.

---

## 7. Running Individual Modules & Tests

All commands run from the repository root with the virtual environment active.

| What | Command |
|---|---|
| Master run | `python main.py` |
| Memory module end-to-end demo (needs Pinecone) | `python -m Memory_module.demo` |
| Memory module test suite | `python -m unittest discover -s tests -v` |
| Standalone chat app (submodule) | `python "chat_module/Chat Module/App/main.py"` |
| Standalone research demo (LangSearch) | `python research_module/research.py` |
| Architect without chat front door | `python "The architect/Architect_logic.py"` |

- `python -m Memory_module.demo` creates a Pinecone index on first run (~1 minute) and
  cleans up its demo user when done. See `LIVE_TESTING.md` for the full live-testing
  procedure against real Pinecone.
- `python research_module/research.py` is an interactive demo that requires the
  `openai` package and `SEARCH_API_KEY` (LangSearch API). It is **not** part of the
  orchestrator — the registered research worker is `researchmodu.py`.

---

## 8. Git / Repo Commands

```powershell
# Clone with everything
git clone --recurse-submodules https://github.com/a01802480-hub/All_things_agentic.git

# Get latest changes (main repo + submodules)
git pull --recurse-submodules

# If you cloned without submodules, fetch them now
git submodule update --init --recursive

# Sync submodules to the commit the main repo pins
git submodule update

# Work on a feature branch
git checkout -b feature/my-change
git add .
git commit -m "My change"
git push -u origin feature/my-change

# Check status including submodules
git status
```

**Submodule rule:** `research_module` and `chat_module` are separate repositories.
Edits inside them must be committed and pushed **inside the submodule**, then the main
repo records the new submodule commit. When pulling the main repo, re-run
`git submodule update --init --recursive`.

`.gitignore` already excludes `.env`, virtual environments, `__pycache__/`, and local
memory data (`Memory_module/data/`) — never commit API keys.

---

## 9. Project Structure

```text
All_things_agentic/
├── main.py                      ← MASTER ENTRY POINT
├── requirement.md               ← this document
├── README.md
├── LIVE_TESTING.md              ← Pinecone live-testing procedure
├── .env                         ← your local keys (gitignored)
├── .env.example                 ← template for required variables
├── The architect/
│   ├── chat_to_architect.py     ← ChatAnalyzer front door
│   ├── Architect_logic.py       ← Gemini planner + task orchestrator
│   └── generated_modules/       ← reserved for dynamically created tools
├── research_module/             ← git submodule (Resarch-Module)
│   ├── researchmodu.py          ← registered worker (execute)
│   └── research.py              ← standalone LangSearch demo
├── writing_module/
│   └── writing_module.py        ← WriterAgent → outputs/*.tex
├── clarity_module/
│   └── clairty_module.py        ← ClarityAgent editor
├── programing_module/
│   └── programing_module.py     ← empty placeholder (not registered yet)
├── chat_module/                 ← git submodule (All_things_agentic chat)
├── Memory_module/               ← Pinecone memory subsystem
│   ├── memory_logic.py          ← MemoryManager public API
│   ├── long_memory.py / short_memory.py
│   ├── demo.py                  ← python -m Memory_module.demo
│   └── requirements.txt
├── tests/
│   └── test_memory_module.py    ← unittest suite
└── outputs/                     ← generated reports (gitignored data)
```

**Worker discovery convention:** the Architect scans every folder ending in `_module`
for `.py` files exposing an `async def execute(query, context)` function (or an agent
instance with `.execute`). To add a new agent, drop a `*_module/your_module.py` file with
an `execute` function — it is registered automatically at next boot.

---

## 10. Troubleshooting / Known Issues

1. **`CRITICAL: GEMINI_API_KEY not found`** — the Architect exits at boot. Create/check
   `.env` in the repo root and confirm with the key-loaded check in §5.4.
2. **A task fails with "Agent ... is missing or failed to load"** — the module isn't in a
   `_module` folder or has no `execute` function. Check the boot log for
   `[Registry]` errors (missing library or syntax error in the file).
3. **⚠️ `research_module/research.py` is a boot hazard if `openai` is installed.**
   That file runs `input()` and a search **at module level** (no `if __name__ ==
   "__main__"` guard). The registry imports every `.py` in `_module` folders at boot, so
   installing `openai` (needed by that demo) will make the registry prompt you during
   startup. It is currently skipped with a "Missing Library" log because `openai` is not
   installed. Keep `openai` uninstalled for the master run, or wrap that file's demo code
   in a `__main__` guard.
4. **`programing_module.py` is empty (0 bytes)** — it is a placeholder and never
   registers; the planner will simply not be able to assign it tasks.
5. **PowerShell blocks `.venv\Scripts\Activate.ps1`** — run
   `Set-ExecutionPolicy -Scope Process Bypass` once in that terminal.
6. **Pinecone `401`/`403`, missing key, or dimension mismatch** — see the full
   troubleshooting table in `LIVE_TESTING.md` (key placement, index cloud/region,
   `Vector dimension 1536 does not match...`).
7. **Memory backend shows `local` instead of `pinecone`** — the key wasn't loaded;
   the module silently fell back to local storage. Fix `.env` before treating results
   as live.
8. **`python main.py` on Windows** — no event-loop flags needed; `main.py` already
   applies `WindowsSelectorEventLoopPolicy`. If you embed the Architect elsewhere on
   Windows, apply the same policy.

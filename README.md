# All Things Agentic: Modular Multi-Agent Framework

This repository contains the architecture, starter code, and evaluation framework developed for the **All Things Agentic Hackathon**. Initially structured as the foundation for our internal STEM group qualifier competition, it features multi-phase challenge setups designed to test and select the final three-person hackathon team.

## Architecture Principles

The core design philosophy of this project is **strict modularity**. The system is built out of entirely independent modules rather than a monolithic, tightly coupled codebase. 

- **Self-Contained Execution:** Every agent and sub-module is designed to be complete within itself. 
- **Decoupled Logic:** Components do not bleed logic into one another. They can be tested, run, and upgraded in isolation.
- **Centralized Orchestration:** Individual modules are designed to be plugged into a higher-level module—the **Architect**—which coordinates the overarching workflow without interfering with the internal operations of the agents.

## 🧩 Core Modules

### 1. The Architect
The high-level controller of the system. It does not execute specific granular tasks but instead manages the routing, inputs, and outputs between the various independent agents.

### 2. Adaptive AI Chatbot
A fully self-contained chatbot module built to handle the dynamic, **adaptive AI chats** required for the hackathon challenges. It maintains its own internal behavior and state, slotting perfectly into the Architect when user interaction is required.

### 3. Memory Module
This module is strictly dedicated to state and context retention. Its logic is isolated exclusively for memory management and is intentionally *not* connected to everything else. It serves as a plug-in component for the Architect, ensuring that memory management remains highly targeted and clean.

### 4. Research Agent
An autonomous agent built to gather, synthesize, and report information. Just like the chatbot, it functions completely independently, completing its research workflows internally before returning the finalized data to the Architect.

## 🚀 Getting Started (Windows Environment)

This environment and the starter code are optimized for Windows setups. 

### Prerequisites
* Python 3.9+
* Git

### Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/a01802480-hub/All_things_agentic.git](https://github.com/a01802480-hub/All_things_agentic.git)

## 🧪 Reproducible Testing

The repository ships a deterministic, offline test suite so results can be reproduced on any machine without API keys, external services, or network access.

### 1. Set up the environment
From the repository root:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run this once in the current terminal:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 2. Run the full test suite
From the repository root:
```powershell
python -m unittest discover -s tests -v
```

Expected output (all tests must pass):
```text
test_public_workflow_without_pinecone ... ok

----------------------------------------------------------------------
Ran 1 test in 0.054s

OK
```

### 3. Run a single test module
```powershell
python -m unittest tests.test_memory_module -v
```

> **Note:** Always run tests from the repository root (as `-m unittest`). Executing the file directly (`python tests\test_memory_module.py`) fails because the module imports require the root on `sys.path`.

### Reproducibility notes
- The memory smoke test runs against the **local JSON backend** (`use_pinecone=False`) inside a temporary directory — no Pinecone account or API key is required, and no data is left behind after the run.
- Timings in the output vary between machines; only the `ok` / `OK` status matters.
- Live end-to-end testing against a real Pinecone index (requires an API key and network access) is documented separately in [LIVE_TESTING.md](LIVE_TESTING.md).

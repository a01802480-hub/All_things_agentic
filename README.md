# All Things Agentic: Modular Multi-Agent Framework

Repository for the Hackaton "All things agentic" Sponsored by Google. 
This repository contains the architecture, starter code, and evaluation framework developed for the **All Things Agentic Hackathon**. It features multi-phase challenge setups designed to test and select the final three-person hackathon team.

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

### 5. Other agents
This is for any and all modules that are considered important or relevant to the project. As the other modules, it must function completley independently, completeing its tasks internally and returning to the Architect

## 🚀 Getting Started (Windows Environment)

This environment and the starter code are optimized for Windows setups. 

### Prerequisites
* Python 3.9+
* Git

### Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/a01802480-hub/All_things_agentic.git](https://github.com/a01802480-hub/All_things_agentic.git)

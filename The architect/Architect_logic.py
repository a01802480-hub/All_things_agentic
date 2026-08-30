import asyncio
import logging
import json
import os
import sys
import importlib.util
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

# NEW IMPORTS FOR REAL LLM INTEGRATION
from dotenv import load_dotenv
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TheArchitect")

# Resolve absolute paths based on the current file location
# This assumes Architect_logic.py is inside 'The architect' folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) # Go up one level to 'All_things_agentic'

# The folder where the CodeAgent will save new tools
GENERATED_MODULES_DIR = os.path.join(CURRENT_DIR, "generated_modules")
os.makedirs(GENERATED_MODULES_DIR, exist_ok=True)

# Add project root to sys.path so we can import from sibling directories if needed
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class SubTask(BaseModel):
    task_id: str
    description: str
    required_agent: str
    dependencies: List[str] = Field(default_factory=list)
    status: str = "PENDING"
    result: Optional[str] = None
    error: Optional[str] = None

class ExecutionState(BaseModel):
    main_goal: str
    tasks: Dict[str, SubTask] = Field(default_factory=dict)
    global_status: str = "PLANNING"
    shared_context: Dict[str, Any] = Field(default_factory=dict)

class DynamicToolRegistry:
    """
    Scans the entire project tree for directories ending with '_module',
    loads them dynamically using importlib, and registers their capabilities.
    """
    def __init__(self):
        self.workers: Dict[str, Callable] = {}
        self.discover_all_modules()

    def discover_all_modules(self):
        logger.info(f"[Registry] Commencing deep scan of project root: {PROJECT_ROOT}")
        
        # 1. Scan the root for directories ending in '_module' (e.g., research_module)
        for item in os.listdir(PROJECT_ROOT):
            item_path = os.path.join(PROJECT_ROOT, item)
            if os.path.isdir(item_path) and item.endswith("_module"):
                self._scan_directory_for_py_files(item_path)

        # 2. Scan the local generated_modules directory
        self._scan_directory_for_py_files(GENERATED_MODULES_DIR)

    def _scan_directory_for_py_files(self, directory: str):
        logger.info(f"[Registry] Scanning directory: {directory}")
        if not os.path.exists(directory):
            return

        for filename in os.listdir(directory):
            # We are looking for python files that represent the core logic of that module.
            # Avoid tests, inits, and the Architect itself.
            if filename.endswith(".py") and filename != "__init__.py" and not filename.startswith("test_"):
                module_name = filename[:-3] # Remove .py
                filepath = os.path.join(directory, filename)
                self.load_and_register(module_name, filepath)

    def load_and_register(self, module_name: str, filepath: str):
        try:
            # Using importlib to dynamically load the file without hardcoding imports
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Convention 1: The module has a standard 'execute' async function
                if hasattr(module, 'execute'):
                    self.workers[module_name] = module.execute
                    logger.info(f"[Registry] Registered standard function module: {module_name} from {filepath}")
                
                # Convention 2: The module exposes an agent instance (e.g., research_agent)
                elif hasattr(module, f"{module_name.split('_')[0]}_agent"):
                    agent_instance = getattr(module, f"{module_name.split('_')[0]}_agent")
                    if hasattr(agent_instance, 'execute'):
                        self.workers[module_name] = agent_instance.execute
                        logger.info(f"[Registry] Registered agent class module: {module_name} from {filepath}")
                
                # Convention 3: For things like memory_logic which might not have an 'execute'
                # but might have specific manager classes.
                else:
                    logger.debug(f"[Registry] {filename} loaded, but missing an 'execute' callable. Skipping direct agent registration.")
        except Exception as e:
            logger.error(f"[Registry] Failed to load {filepath}: {e}")

    def get_worker(self, name: str) -> Optional[Callable]:
        # Fuzzy match to allow the LLM to request "research" instead of "research_module"
        for registered_name, worker in self.workers.items():
            if name.lower() in registered_name.lower():
                return worker
        return None

class Architect:
    def __init__(self):
        self.registry = DynamicToolRegistry()
        self.user_id = "default_user_1"
        
        # Load environment variables from both root and local folders
        load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
        load_dotenv(os.path.join(CURRENT_DIR, ".env"))
        load_dotenv()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("[Architect] CRITICAL: GEMINI_API_KEY not found! Check your .env file.")
            raise ValueError("Cannot initialize Orchestrator without a GEMINI_API_KEY.")
            
        self.ai_client = genai.Client(api_key=api_key)

    def _get_available_tools_string(self) -> str:
        if not self.registry.workers:
            return "No modules discovered."
        return ", ".join(self.registry.workers.keys())

    async def _generate_execution_plan(self, goal: str) -> str:
        """
        Uses Groq to analyze the goal and generate a JSON task graph (DAG).
        It is fully aware of what tools/modules are currently available on disk.
        """
        available_tools = self._get_available_tools_string()
        logger.info(f"[Architect] Planning phase. Providing Groq with tools: {available_tools}")
        
        prompt = f"""
        You are the Master Orchestrator Agent. Your job is to break the user's goal into a logical sequence of sub-tasks.
        
        Available backend worker modules: [{available_tools}]
        
        User Goal & Context:
        {goal}
        
        CRITICAL RULES:
        1. Only assign tasks to the exact module names listed above.
        2. If a required capability is completely missing, do your best to use existing modules or create a generic task.
        3. Output MUST be a valid JSON object containing a "tasks" array.
        
        Output format:
        {{
          "tasks": [
            {{
              "task_id": "t1", 
              "description": "Clear instruction for the worker", 
              "required_agent": "module_name", 
              "dependencies": []
            }}
          ]
        }}
        """
        
        # Call Gemini asynchronously, enforcing JSON mode
        response = await self.ai_client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        logger.info("[Architect] LLM generated the execution plan.")
        return response.text

    async def execute_workflow(self, state: ExecutionState):
        logger.info("--- ARCHITECT EXECUTING WORKFLOW ---")
        
        while state.global_status == "EXECUTING":
            ready_tasks = []
            for task_id, task in state.tasks.items():
                if task.status == "PENDING":
                    deps_met = all(state.tasks[dep].status == "COMPLETED" for dep in task.dependencies)
                    if deps_met:
                        ready_tasks.append(task)
            
            if not ready_tasks:
                pending = [t for t in state.tasks.values() if t.status in ["PENDING", "IN_PROGRESS"]]
                if not pending:
                    state.global_status = "COMPLETED"
                else:
                    state.global_status = "FAILED"
                break

            for t in ready_tasks:
                t.status = "IN_PROGRESS"

            # Parallel Execution using dynamically discovered callables
            async_coroutines = []
            for t in ready_tasks:
                worker_func = self.registry.get_worker(t.required_agent)
                if not worker_func:
                    logger.error(f"[Architect] Requested module '{t.required_agent}' not found in Registry.")
                    t.status = "FAILED"
                    continue
                
                # Context passing
                context = {"memory": state.shared_context}
                for dep in t.dependencies:
                     context[dep] = state.tasks[dep].result
                     
                async_coroutines.append(self._run_task_safely(worker_func, t, context))
            
            await asyncio.gather(*async_coroutines)

    async def _run_task_safely(self, worker_func: Callable, task: SubTask, context: dict):
        try:
            logger.info(f"[Architect] Firing dynamic module for task: {task.task_id}")
            # Handling both async and sync execute functions gracefully
            if asyncio.iscoroutinefunction(worker_func):
                result = await worker_func(query=task.description, context=context)
            else:
                # If a dynamically written module happens to be synchronous
                result = await asyncio.to_thread(worker_func, task.description, context)
            
            task.result = result
            task.status = "COMPLETED"
        except Exception as e:
            task.error = str(e)
            task.status = "FAILED"
            logger.error(f"[Architect] Module failed on {task.task_id}: {e}")

    async def process_chat(self, user_chat: str):
        logger.info(f"\n--- ARCHITECT INITIATED ---")
        logger.info(f"Goal: '{user_chat}'")

        # 1. Attempt to load memory preferences if the Memory_module is available
        historical_preferences = {}
        try:
            # Because we added PROJECT_ROOT to sys.path, we can import it like this
            from Memory_module.memory_logic import MemoryManager # Adjust import based on your exact class names
            historical_preferences = MemoryManager().get_user_profile(self.user_id)
            logger.info(f"[Architect] Loaded historical preferences: {historical_preferences}")
        except ImportError as e:
            logger.warning(f"[Architect] Memory logic not directly importable: {e}. Proceeding without memory context.")

        state = ExecutionState(main_goal=user_chat, shared_context={"preferences": historical_preferences})

        # 2. Plan based on discovered tools (Now using the real LLM!)
        try:
            plan_json = await self._generate_execution_plan(state.main_goal)
            
            # Parse the JSON and build the DAG
            plan_data = json.loads(plan_json)
            tasks_list = plan_data.get("tasks", [])
            for t in tasks_list:
                state.tasks[t["task_id"]] = SubTask(**t)
            state.global_status = "EXECUTING"
            
        except Exception as e:
            logger.error(f"[Architect] Planning failed! Error: {e}")
            state.global_status = "FAILED"
            return state

        # 3. Execute
        await self.execute_workflow(state)
        
        logger.info(f"--- ARCHITECT WORKFLOW COMPLETE ---")
        for task_id, task in state.tasks.items():
            if task.status == "COMPLETED":
                logger.info(f"Task {task_id} Output: {task.result}")
        return state

if __name__ == "__main__":
    architect = Architect()
    user_prompt = "Find out everything about quantum error correction and summarize it."
    asyncio.run(architect.process_chat(user_prompt))
import os
import sys
import json
import logging
import uuid
import asyncio
import hashlib
import importlib.util
import importlib.machinery
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from time import timezone


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TheArchitect")

GENERATED_MODULES_DIR = Path(__file__).parent / "generated_modules"
os.makedirs(GENERATED_MODULES_DIR, exist_ok=True)

class ToolsRegistry:
    def __init__(self):
        self.tools = {}
        
    def register_dynamical(self, name: str, tool: Any) -> None:
        self.tools[name] = tool
        logger.info(f"Dynamically registered tool: {name}")
    def register_tool(self, name: str, tool: Any) -> None:
        self.tools[name] = tool
        logger.info(f"Registered tool: {name}")
    def get_tool(self, name: str) -> Optional[Any]:
        return self.tools.get(name)
    def list_tools(self) -> List[str]:
        return list(self.tools.keys()) 
class tool_creation_request(BaseModel):
    tool_name: str
    tool_code: str
    async def handle_generation_request(self) -> None:
        task_description = f"Create a new tool named {self.tool_name} with the provided code."
        logger.info(f"Handling tool creation request: {task_description}")
    async def create_tool(self) -> None:
        tool_path = GENERATED_MODULES_DIR / f"{self.tool_name}.py"
        with open(tool_path, "w") as f:
            f.write(self.tool_code)
        logger.info(f"Tool {self.tool_name} created at {tool_path}")
        # Dynamically import the newly created tool
        spec = importlib.util.spec_from_file_location(self.tool_name, tool_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.tool_name] = module
        spec.loader.exec_module(module)
        logger.info(f"Tool {self.tool_name} imported successfully")
    

class subtask(BaseModel):
    task_id: str
    description: str
    required_agent: str
    is_tool_creation: bool = False # NEW: Flag to tell orchestrator to inject this
    tool_name_to_create: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    status: str = "PENDING"
    result: Optional[str] = None
class exexutor_state(BaseModel):
    main_task: str
    tasks: List[subtask] = Field(default_factory=list)
    completed_tasks: List[subtask] = Field(default_factory=list)
    failed_tasks: List[subtask] = Field(default_factory=list)
    Global_status: str = "PENDING"
class base_worker(BaseModel):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.subtasks: List[subtask] = []
    async def execute_subtask(self, subtask: subtask) -> None:
        logger.info(f"[{self.name}] Started task {task.task_id}")
        # Simulate some work being done
        await asyncio.sleep(1)
        subtask.status = "completed"
        subtask.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"[{self.name}] completed subtask {subtask.name}")
        
        if self.subtasks:
            next_subtask = self.subtasks.pop(0)
            await self.execute_subtask(next_subtask)
        if self.name in self.workers:
            return state.tasks.pop(0)
        return subtask
        
        
class architect:
    def __init__(self, workers: list[base_worker] ):
        self.workers = {w.name: w for w in workers}    
    def get_worker_resume(self) -> str:
        return "\n".join([f"{w.name}: {w.description}" for w in self.workers.values()])
    async def planner_llm(self, task_description: str) -> List[subtask]:
        # Placeholder for LLM planning logic
        # In a real implementation, this would call an LLM to generate subtasks based on the task description
        logger.info(f"Planning subtasks for task: {task_description}")
        return [subtask(name=f"Subtask {i+1}", description=f"Description for subtask {i+1}") for i in range(3)]
    async def assign_task(self, worker_name: str, task: subtask) -> None:
        if worker_name in self.workers:
            worker = self.workers[worker_name]
            worker.subtasks.append(task)
            logger.info(f"Assigned task {task.name} to worker {worker_name}")
            await worker.execute_subtask(task)
        else:
            logger.error(f"Worker {worker_name} not found")
    #def assign_task(self, worker_name: str, task: subtask) -> None:
            #if worker_name in self.workers:
             #   worker = self.workers[worker_name]
              #  worker.subtasks.append(task)
               # logger.info(f"Assigned task {task.name} to worker {worker_name}")
            #else:
             #   logger.error(f"Worker {worker_name} not found")
    async def plan_workflow(self, task_description: str) -> None:
        logger.info(f"Planning workflow for task: {task_description}")
        promt=f"""
        Goal: {task_description}
        Available workers: {self.get_worker_resume()}
        """
        plan_json = await self.planner_llm(promt) 
        tasks_data=json.loads(plan_json)
        for task_data in tasks_data:
           state.tasks[task_data['task_id']] = subtask(**task_data)
           state.global_status = "EXECUTING"
    async def execute_workflow(self, state: exexutor_state) -> None:
        logger.info("Executing workflow")
        while state.global_status == "EXECUTING" and state.tasks:
            ready_tasks = [task for task in state.tasks.values() if all(dep in [t.task_id for t in state.completed_tasks] for dep in task.dependencies)]
           
            for task_id, task in state.tasks.items():
                if task.status == "PENDING":
                    deps_met = all(state.tasks[dep].status == "COMPLETED" for dep in task.dependencies)
                    if deps_met:
                        ready_tasks.append(task)
            if not_ready_tasks:
                pending = [t for t in state.tasks.values() if t.status in ["PENDING", "IN_PROGRESS"]]
                if not pending:
                    state.global_status = "COMPLETED"
                    logger.info("All tasks completed.")
                else:
                        # If tasks are pending but none are ready, it means dependencies failed or deadlock.
                    logger.error("Deadlock or dependency failure detected!")
                    state.global_status = "FAILED"
                break
            for t in ready_tasks:
                t.status = "IN_PROGRESS"
            async_coroutines = []
            for t in ready_tasks:
                # Assign tasks to workers based on some logic (e.g., round-robin, load balancing)
                worker_name = self.select_worker_for_task(t)
                if not worker_name:
                    logger.error(f"No available worker for task {t.task_id}")
                    t.status = "FAILED"
                    state.failed_tasks.append(t)
                    continue
                context = {dep: state.tasks[dep].result for dep in t.dependencies}
                async_coroutines.append(self._run_single_task(worker, t, context))
            await asyncio.gather(*async_coroutines)

    async def _run_single_task(self, worker: base_worker, task: subtask, context: Dict[str, Any]) -> None:
        try:
            result = await self.execute_task(worker.name, task, context)
            task.result = result
            task.status = "COMPLETED"
            logger.info(f"Task {task.task_id} completed successfully.")
        except Exception as e:
            task.error = str(e)
            task.status = "FAILED"
            logger.error(f"Task {task.task_id} failed with error: {e}")
async def main():
    # Example usage
    workers = [
        base_worker(name="Worker1", description="Handles data processing tasks"),
        base_worker(name="Worker2", description="Handles API calls and external integrations"),
    ]
    arch = architect(workers=workers)
    goal = "Develop a new feature for the application"
    await arch.plan_workflow(goal)
     
    print("\n" + "="*40)
    print("FINAL EXECUTION REPORT")
    print("="*40)
    for task_id, task in final_state.tasks.items():
        print(f"[{task.status}] {task_id} ({task.required_agent}): {task.description}")
        if task.status == "COMPLETED":
            print(f"    Result: {task.result}")

if __name__ == "__main__":
    asyncio.run(main())
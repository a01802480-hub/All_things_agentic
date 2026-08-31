import logging
import asyncio
import os
import sys
import tempfile
import traceback
from typing import Dict, Any

logger = logging.getLogger("ExecutionAgent")

async def execute(query: str, context: Dict[str, Any] = None) -> str:
    """
    The Execution Agent: Takes raw Python code (usually passed in context from a Programming Agent),
    saves it to a temporary file, and runs it safely in an isolated subprocess.
    """
    context = context or {}
    logger.info(f"[ExecutionAgent] Received execution request for: '{query}'")

    # 1. Locate the code to execute
    code_to_run = None
    
    # Check if the code was passed directly in the query (unlikely, but possible)
    if "```python" in query:
        code_to_run = _extract_code(query)
        
    # Check context dependencies
    if not code_to_run:
        for task_id, task_result in context.items():
            if task_id != "memory" and isinstance(task_result, str):
                if "```python" in task_result:
                    code_to_run = _extract_code(task_result)
                    logger.info(f"[ExecutionAgent] Found code to execute from dependency {task_id}")
                    break

    if not code_to_run:
        error_msg = "⚠️ ERROR: No Python code block found in the query or context to execute."
        logger.error(f"[ExecutionAgent] {error_msg}")
        return error_msg

    logger.info("[ExecutionAgent] Preparing isolated execution environment...")

    # 2. Write code to a temporary file
    # We use a temp directory to keep things clean and avoid cluttering the project
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_script_path = os.path.join(temp_dir, "generated_script.py")
            
            with open(temp_script_path, "w", encoding="utf-8") as f:
                f.write(code_to_run)
                
            logger.info(f"[ExecutionAgent] Code written to temporary file: {temp_script_path}")

            # 3. Execute the script in a subprocess
            # This is CRITICAL for stability. If the generated script has an infinite loop
            # or a syntax error, it won't crash our entire Orchestrator process.
            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir # Run it inside the temp directory
            )

            logger.info("[ExecutionAgent] Subprocess launched. Waiting for completion...")
            
            # Put a timeout on the execution to prevent infinite loops from hanging the system
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                process.kill()
                error_msg = "⚠️ ERROR: Execution timed out after 30 seconds (Possible infinite loop)."
                logger.error(f"[ExecutionAgent] {error_msg}")
                return error_msg

            # 4. Process the results
            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            if process.returncode == 0:
                logger.info("[ExecutionAgent] Execution completed successfully.")
                result_output = f"--- EXECUTION SUCCESS ---\n"
                if stdout_str:
                    result_output += f"Output:\n{stdout_str}\n"
                else:
                    result_output += "Script ran successfully but produced no standard output.\n"
                result_output += "-------------------------"
                return result_output
            else:
                logger.warning(f"[ExecutionAgent] Execution failed with return code {process.returncode}")
                error_output = f"⚠️ ERROR: Execution Failed (Return Code {process.returncode})\n"
                if stdout_str:
                    error_output += f"Standard Output:\n{stdout_str}\n"
                if stderr_str:
                    error_output += f"Standard Error:\n{stderr_str}\n"
                return error_output

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[ExecutionAgent] Critical failure during execution preparation: {e}\n{error_details}")
        return f"⚠️ ERROR: Execution Agent encountered a critical issue: {e}"

def _extract_code(text: str) -> str:
    """Helper function to extract code from markdown blocks."""
    import re
    match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1)
    
    # Fallback if the closing backticks are missing
    if "```python" in text:
        parts = text.split("```python")
        if len(parts) > 1:
            return parts[1].replace("```", "").strip()
            
    return ""
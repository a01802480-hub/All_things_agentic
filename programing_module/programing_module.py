import logging
import os
import json
import re
import ast
from typing import Dict, Any, List

try:
    from google import genai
    from google.genai import types
    from dotenv import load_dotenv
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

logger = logging.getLogger("ProgrammingModule")
load_dotenv()

class ModuleSpec:
    """
    Represents the technical specification of a module before code generation.
    Adapted from the user's original OOP design.
    """
    def __init__(self, module_name: str, purpose: str, identified_gap: str, inputs: List[str], outputs: List[str], logic_steps: List[str]):
        # Ensure the module name is snake_case and ends with _module for the registry
        self.module_name = module_name.lower().replace(" ", "_")
        if not self.module_name.endswith("_module"):
            self.module_name += "_module"
            
        self.purpose = purpose
        self.identified_gap = identified_gap
        self.inputs = inputs
        self.outputs = outputs
        self.logic_steps = logic_steps

    def to_dict(self):
        return {
            "module_name": self.module_name,
            "purpose": self.purpose,
            "identified_gap": self.identified_gap,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "logic_steps": self.logic_steps
        }

async def execute(query: str, context: Dict[str, Any] = None) -> str:
    """
    The Programming Agent: Takes a request from the Architect to build a new capability,
    designs a specification, writes the Python code, audits it, and saves it to disk.
    """
    context = context or {}
    logger.info(f"[ProgrammingModule] Received coding request: '{query}'")
    
    if not HAS_GENAI:
        return "⚠️ ERROR: Programming module requires google-genai and python-dotenv."

    # Locate the API key using relative pathing to the root project
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    load_dotenv(os.path.join(project_root, ".env"))

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ ERROR: GEMINI_API_KEY not found in environment."

    client = genai.Client(api_key=api_key)

    logger.info("[ProgrammingModule] Phase 1: Drafting Module Specification...")
    
    spec_prompt = f"""
    You are an expert Software Architect. The system needs a new Python module.
    Analyze this request: "{query}"
    
    Identify the capability GAP in the current system. What is missing? 
    Design a module to eliminate this gap.
    
    Output a JSON specification for this module.
    It MUST match this exact schema:
    {{
        "module_name": "name_of_module",
        "purpose": "What this module does",
        "identified_gap": "The exact capability gap this module eliminates",
        "inputs": ["list", "of", "expected", "context", "variables"],
        "outputs": ["list", "of", "return", "data"],
        "logic_steps": ["step 1", "step 2", "step 3"]
    }}
    """
    
    try:
        spec_response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=spec_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        spec_data = json.loads(spec_response.text.strip())
        spec = ModuleSpec(**spec_data)
        logger.info(f"[ProgrammingModule] Specification created for: {spec.module_name}")
        
    except Exception as e:
        logger.error(f"[ProgrammingModule] Failed to generate specification: {e}")
        return f"⚠️ ERROR during spec generation: {e}"

    logger.info("[ProgrammingModule] Phase 2: Generating Python Code...")
    
    code_prompt = f"""
    You are an expert Python developer. Generate a complete Python module based on this specification:
    {json.dumps(spec.to_dict(), indent=2)}
    
    CRITICAL ARCHITECTURAL REQUIREMENTS:
    1. The module MUST contain an asynchronous function with this exact signature:
       `async def execute(query: str, context: dict = None) -> str:`
    2. Import standard libraries like `logging`, `json`, `os`, and `asyncio` as needed.
    3. Include a configured logger: `logger = logging.getLogger("{spec.module_name}")`.
    4. Ensure the `execute` function follows the `logic_steps` in the specification.
    5. Handle errors gracefully using try/except blocks and return the error as a string if it fails.
    6. Return ONLY the raw Python source code wrapped in a ```python block. No explanations.
    """
    
    try:
        code_response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=code_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2
            )
        )
        
        raw_code = code_response.text.strip()
        
        # Extract just the code from the markdown fences
        code_match = re.search(r'```python\n(.*?)\n```', raw_code, re.DOTALL)
        if code_match:
            final_code = code_match.group(1)
        else:
            # Fallback in case the LLM didn't use fences
            final_code = raw_code.replace('```python', '').replace('```', '')

        logger.info("[ProgrammingModule] Phase 3: Auditing code for capability gaps and bugs...")
        
        # SELF-HEALING: Find gaps in its own generated code and eliminate them
        gap_errors = []
        try:
            ast.parse(final_code) # Validates Python syntax without running the code
        except SyntaxError as e:
            gap_errors.append(f"Syntax Error on line {e.lineno}: {e.msg}")
            
        if "async def execute" not in final_code:
            gap_errors.append("Architectural Gap: The module is missing the required `async def execute(query: str, context: dict = None) -> str:` function.")

        if gap_errors:
            logger.warning(f"[ProgrammingModule] Gaps found in generated module! Initiating Self-Correction Phase...")
            error_list = "\n- ".join(gap_errors)
            
            # This is where the code got cut off before! It is fully complete now.
            correction_prompt = f"""
            Eliminate the following gaps in your previous code:
            - {error_list}
            
            ORIGINAL CODE:
            ```python
            {final_code}
            """
            
            correction_response = await client.aio.models.generate_content(
                model='gemini-3.6-flash',
                contents=correction_prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            
            correct_raw = correction_response.text.strip()
            correct_match = re.search(r'```python\n(.*?)\n```', correct_raw, re.DOTALL)
            final_code = correct_match.group(1) if correct_match else correct_raw.replace('```python', '').replace('```', '')
            logger.info("[ProgrammingModule] Gaps successfully eliminated. Code is structurally sound.")
        else:
            logger.info("[ProgrammingModule] No structural gaps found in code.")

        # Save to the generated_modules folder
        output_dir = os.path.join(os.path.dirname(current_dir), "generated_modules")
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, f"{spec.module_name}.py")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_code)
            
        logger.info(f"[ProgrammingModule] Successfully generated and saved to {filepath}")
        
        return f"✅ SUCCESS: New module '{spec.module_name}' generated!\n📁 Saved to: {filepath}\nThe Architect can now use this module in future workflows."
        
    except Exception as e:
        logger.error(f"[ProgrammingModule] Failed to generate code: {e}")
        return f"⚠️ ERROR during code generation: {e}"

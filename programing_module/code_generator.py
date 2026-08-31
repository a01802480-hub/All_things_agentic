import json


class CodeGenerator:
    """
    Generates Python source code from a ModuleSpec.
    """

    def __init__(self, llm_provider):
        self.llm = llm_provider

    def generate(self, module_spec):
        prompt = f"""
You are an expert Python developer.

Generate a complete Python module based on the following specification.

MODULE NAME:
{module_spec.module_name}

PURPOSE:
{module_spec.purpose}

INPUTS:
{module_spec.inputs}

OUTPUTS:
{module_spec.outputs}

METHODS:
{json.dumps(module_spec.methods, indent=2)}

DEPENDENCIES:
{module_spec.dependencies}

Requirements:
- Generate valid Python code.
- Use clean, modular Python.
- Include a class named exactly {module_spec.module_name}.
- Implement all methods described in the specification.
- Include docstrings.
- Do not use external dependencies unless explicitly listed.
- Do not include markdown.
- Return ONLY the Python source code.
"""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Python developer who creates "
                    "modular components for AI agent systems."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        response = self.llm.generate_response(messages)

        # In case the LLM accidentally returns markdown fences
        code = response.strip()

        if code.startswith("```python"):
            code = code[len("```python"):].strip()

        if code.startswith("```"):
            code = code[3:].strip()

        if code.endswith("```"):
            code = code[:-3].strip()

        return code
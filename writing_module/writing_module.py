import logging
import os
from typing import Dict, Any

try:
    from google import genai
    from google.genai import types
    from dotenv import load_dotenv
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

load_dotenv()
logger = logging.getLogger("WriterAgent")

async def execute(query: str, context: Dict[str, Any] = None) -> str:
    """
    The Writer Agent: Takes research data gathered by other modules (via context)
    and uses an LLM to synthesize it into a highly detailed, comprehensive academic report.
    """
    context = context or {}
    logger.info(f"[WriterAgent] Received synthesis task: '{query}'")
        
    if not HAS_GENAI:
        return "⚠️ ERROR: Writer module requires google-genai and python-dotenv."

    # Search for the API key in multiple possible locations
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    load_dotenv(os.path.join(project_root, ".env"))

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ ERROR: GEMINI_API_KEY not found in environment."

    # Extract all the data gathered by the research modules from the dependency context
    compiled_research = ""
    for dep_task_id, dep_result in context.items():
        if dep_task_id != "memory" and dep_result:
            compiled_research += f"\n--- Data from {dep_task_id} ---\n{dep_result}\n"

    if not compiled_research.strip():
        compiled_research = "No prior research data was provided by the dependencies."

    logger.info("[WriterAgent] Compiling full academic report using Gemini...")

    # We drastically expand the prompt to force the LLM to write a lengthy, structured document
    prompt = f"""
    You are an expert academic Synthesizer and Technical Writer.
    Your task is to write a highly detailed, comprehensive, and exhaustive academic report based strictly on the provided research data.
        
    User Request / Task: {query}
        
    Provided Research Data:
    {compiled_research}
        
    CRITICAL INSTRUCTIONS FOR LENGTH AND DEPTH:
    1. DO NOT summarize briefly. You must expand heavily on every concept, mathematical formula, and physics principle provided in the research.
    2. Explain the "why" and "how" behind the data. If formulas are present, explain their variables and implications in detail step-by-step.
    3. The report MUST be structured like a formal academic paper containing:
       - Title
       - Abstract (Executive Summary)
       - Introduction
       - Detailed Main Body (with multiple well-defined subsections)
       - Analysis / Mathematical Framework
       - Conclusion
       - References (based on the provided snippets)
        
    CRITICAL INSTRUCTIONS FOR FORMATTING:
    1. You MUST ALWAYS output the entire report as a fully compilable LaTeX document, regardless of the content. 
       - Start with \\documentclass{{article}}
       - Include standard packages (\\usepackage{{amsmath, amssymb, geometry, graphicx}})
       - Use proper sectioning (\\section, \\subsection).
    2. DO NOT wrap your response in markdown code blocks (like ```latex). Output ONLY the raw LaTeX code.
    3. Do NOT hallucinate information outside of the provided research data, but DO use your expert knowledge to stitch the provided facts together elegantly and comprehensively.
    """
    
    try:
        client = genai.Client(api_key=api_key)
        
        # We add configuration to force a massive output token limit and a low temperature for academic precision
        response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=8192,
                temperature=0.25
            )
        )
            
        report_content = response.text.strip()
            
        # Clean up markdown code blocks if the LLM accidentally includes them
        if report_content.startswith("```"):
            report_content = "\n".join(report_content.split("\n")[1:])
        if report_content.endswith("```"):
            report_content = "\n".join(report_content.split("\n")[:-1])
                
        report_content = report_content.strip()
            
        # We now ALWAYS force the file to be saved as a LaTeX document
        file_ext = ".tex"
            
        import time
        output_dir = os.path.join(os.getcwd(), "outputs")
        os.makedirs(output_dir, exist_ok=True)
            
        filename = f"synthesized_report_{int(time.time())}{file_ext}"
        filepath = os.path.join(output_dir, filename)
            
        # Save the file to disk
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        logger.info(f"[WriterAgent] Successfully generated full report and saved to {filepath}")
            
        # Provide a short preview for the terminal
        preview = report_content[:400] + "\n\n... [CONTENT TRUNCATED FOR TERMINAL. SEE FILE FOR FULL REPORT]"
            
        return f" SUCCESS: Full Academic Report generated and saved!\n File Path: {filepath}\n\n--- PREVIEW ---\n{preview}"
            
    except Exception as e:
        logger.error(f"[WriterAgent] Failed to synthesize report: {e}")
        return f"ERROR during report synthesis: {e}"
import logging
import os
from typing import Dict, Any

try:
    from google import genai
    from dotenv import load_dotenv
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

load_dotenv()
logger = logging.getLogger("WriterAgent")

async def execute(query: str, context: Dict[str, Any] = None) -> str:
    """
    The Writer Agent: Takes research data gathered by other modules (via context)
    and uses an LLM to synthesize it into a comprehensive report.
    """
    context = context or {}
    logger.info(f"[WriterAgent] Received synthesis task: '{query}'")
        
    if not HAS_GENAI:
        return "⚠️ ERROR: Writer module requires google-genai and python-dotenv."

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

        logger.info("[WriterAgent] Compiling report using Gemini...")

    prompt = f"""
    You are an expert academic Synthesizer and Technical Writer.
    Your task is to write a comprehensive, well-structured report based strictly on the provided research data.
        
    User Request / Task: {query}
        
    Provided Research Data:
    {compiled_research}
        
    CRITICAL INSTRUCTION:
    1. If the research contains mathematical formulas, physics equations, or structural modeling, you MUST output the entire report as a fully compilable LaTeX document (starting with \\documentclass{{article}}).
    2. If it does NOT contain heavy math, output a professional, well-formatted plain text (.txt) document.
    3. DO NOT wrap your response in markdown code blocks (like ```latex or ```text). Output ONLY the raw document text.
    4. Do NOT hallucinate information outside of the provided research data.
    """
    
    try:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
            
        report_content = response.text.strip()
            
            # Clean up markdown code blocks if the LLM accidentally includes them
        if report_content.startswith("```"):
            report_content = "\n".join(report_content.split("\n")[1:])
        if report_content.endswith("```"):
                report_content = "\n".join(report_content.split("\n")[:-1])
                
        report_content = report_content.strip()
            
            # Determine file type based on content
        is_latex = "\\documentclass" in report_content
        file_ext = ".tex" if is_latex else ".txt"
            
        import time
        output_dir = os.path.join(os.getcwd(), "outputs")
        os.makedirs(output_dir, exist_ok=True)
            
        filename = f"synthesized_report_{int(time.time())}{file_ext}"
        filepath = os.path.join(output_dir, filename)
            
            # Save the file to disk
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        logger.info(f"[WriterAgent] Successfully generated and saved report to {filepath}")
            
            # Provide a short preview for the terminal
        preview = report_content[:400] + "\n\n... [CONTENT TRUNCATED FOR TERMINAL. SEE FILE FOR FULL REPORT]"
            
        return f"✅ SUCCESS: Report generated and saved!\n📁 File Path: {filepath}\n\n--- PREVIEW ---\n{preview}"
            
    except Exception as e:
        logger.error(f"[WriterAgent] Failed to synthesize report: {e}")
        return f"⚠️ ERROR during report synthesis: {e}"
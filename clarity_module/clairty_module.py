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

# Configure local logger for this specific agent
logger = logging.getLogger("ClarityAgent")

async def execute(query: str, context: Dict[str, Any] = None) -> str:
    """
    The Clarity Agent: Acts as an expert editor. Takes complex, technical, 
    or messy context data and rewrites it for maximum logical flow, readability, 
    and clarity, ensuring jargon is explained and structure is intuitive.
    """
    context = context or {}
    logger.info(f"[ClarityAgent] Received clarification task: '{query}'")
        
    if not HAS_GENAI:
        return " ERROR: Clarity module requires google-genai and python-dotenv."

    # Search for the API key in multiple possible locations to prevent pathing bugs
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    load_dotenv(os.path.join(project_root, ".env"))

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return " ERROR: GEMINI_API_KEY not found in environment."

    # Gather all the messy/raw data passed down from previous agents in the graph
    raw_data = ""
    for dep_task_id, dep_result in context.items():
        if dep_task_id != "memory" and dep_result:
            raw_data += f"\n--- Input from {dep_task_id} ---\n{dep_result}\n"

    if not raw_data.strip():
        raw_data = "No prior data was provided. Please clarify the user's direct query."

    logger.info("[ClarityAgent] Processing data through Gemini for clarity enhancement...")

    prompt = f"""
    You are an elite Technical Editor and Clarity Agent.
    Your objective is to take the provided raw data/text and aggressively refine it for maximum clarity, readability, and logical flow.
        
    User Request / Task: {query}
        
    Raw Input Data:
    {raw_data}
        
    CRITICAL INSTRUCTIONS:
    1. Eliminate unnecessary repetition and convoluted phrasing.
    2. If highly technical jargon or heavy mathematics is present, ensure it is introduced logically. Provide brief, intuitive explanations for complex terms so an educated reader can follow along smoothly.
    3. Improve the structural hierarchy (use clear headings, bullet points where appropriate, and strong transition sentences).
    4. Maintain 100% of the factual and mathematical accuracy of the original data. Do NOT dumb it down; make it elegantly accessible.
    5. Output ONLY the finalized, clarified text. Do not include meta-commentary like "Here is the clarified version."
    """
    
    try:
        client = genai.Client(api_key=api_key)
        
        # We use a slightly higher temperature than the Writer (0.3) to allow for creative phrasing/editing, 
        # but keep it low enough to prevent hallucinating new facts.
        response = await client.aio.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )
            
        clarified_content = response.text.strip()
            
        logger.info(f"[ClarityAgent] Successfully clarified and refined the data.")
            
        # Return the polished text so the Orchestrator can pass it to the Writer or the User
        return f"--- CLARIFIED OUTPUT ---\n{clarified_content}"
            
    except Exception as e:
        logger.error(f"[ClarityAgent] Failed to clarify data: {e}")
        return f"⚠️ ERROR during clarity processing: {e}"
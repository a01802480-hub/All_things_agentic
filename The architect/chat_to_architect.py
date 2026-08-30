import asyncio
import logging
import json
from typing import Dict, Any

# Import the Architect from our sibling file in the same directory
from Architect_logic import Architect

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ChatAnalyzer")

class ChatAnalyzer:
    """
    Intercepts raw user chat, extracts the core intent and constraints, 
    and bridges the communication to the Architect orchestrator.
    """
    def __init__(self):
        logger.info("[ChatAnalyzer] Initializing and connecting to the Architect...")
        self.architect = Architect()

    async def analyze_intent(self, raw_chat: str) -> Dict[str, Any]:
        """
        Uses an LLM (mocked here) to figure out exactly what the user wants
        before we bother the main orchestrator.
        """
        logger.info(f"[ChatAnalyzer] Analyzing incoming raw message: '{raw_chat}'")
        await asyncio.sleep(1) # Simulating LLM analysis time
        
        # Mock structured output (Replace with Gemini prompt in hackathon)
        analyzed_data = {
            "original_message": raw_chat,
            "primary_goal": raw_chat, 
            "urgency": "high" if "urgent" in raw_chat.lower() or "asap" in raw_chat.lower() else "normal",
            "extracted_constraints": ["Ensure accurate data", "Check memory preferences"]
        }
        
        logger.info(f"[ChatAnalyzer] Analysis complete. Urgency: {analyzed_data['urgency']}")
        return analyzed_data

    async def handle_incoming_message(self, user_id: str, raw_chat: str):
        """
        The main pipeline: Analyze -> Format -> Execute via Architect
        """
        print("\n" + "="*50)
        print(f"NEW MESSAGE FROM {user_id}")
        print("="*50)
        
        # 1. Analyze the chat
        analysis = await self.analyze_intent(raw_chat)
        
        # 2. Append urgency and constraints to the goal so the Architect plans better
        enhanced_goal = (
            f"Goal: {analysis['primary_goal']} | "
            f"Urgency: {analysis['urgency']} | "
            f"Constraints: {', '.join(analysis['extracted_constraints'])}"
        )
        
        # 3. Ensure the Architect knows who is talking (for memory retrieval)
        self.architect.user_id = user_id
        
        # 4. Hand off to the Orchestrator
        logger.info("[ChatAnalyzer] Handing off enhanced goal to the Architect...")
        final_state = await self.architect.process_chat(enhanced_goal)
        
        return final_state
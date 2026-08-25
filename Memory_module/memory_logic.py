"""
memory_logic.py
A self-contained Memory Core module. 
Can be instantiated by any agent (Chatbot, Researcher, etc.) to manage state and context.
"""

from typing import Dict, Any, List
from short_memory import ShortTermMemory
from long_memory import VectorStore

class MemoryCore:
    def __init__(self, memory_namespace: str):
        """
        memory_namespace allows different agents to isolate their memories 
        (e.g., 'research_agent_01' vs 'chatbot_general').
        """
        self.namespace = memory_namespace
        self.short_memory = ShortTermMemory()
        self.long_memory = VectorStore()

    def add_interaction(self, session_id: str, role: str, content: str) -> None:
        """Purely appends raw data to the short-term buffer."""
        self.short_memory.add_message(session_id, role, content)

    def force_commit_to_long_term(self, user_id: str, topic: str, content: str) -> None:
        """Exposed method for the Orchestrator to explicitly save facts to the Vector DB."""
        self.long_memory.save_note(user_id=user_id, topic=topic, content=content)

    def set_agent_state(self, session_id: str, active_state: List[Dict[str, Any]]) -> None:
        """Allows the overarching agent to save its current task state/plan."""
        self.short_memory.update_active_plan(session_id, active_state)

    def retrieve_working_context(self, session_id: str, user_id: str, current_query: str) -> Dict[str, Any]:
        """
        Returns a packaged context block. The calling agent decides how to inject this 
        into its specific system prompt.
        """
        semantic_memories = self.long_memory.retrieve_context(
            user_id=user_id, 
            current_query=current_query
        )
        recent_history = self.short_memory.get_recent_history(session_id)
        current_state = self.short_memory.get_active_plan(session_id)
        
        return {
            "semantic_memories": semantic_memories,
            "recent_history": recent_history,
            "agent_state": current_state
        }
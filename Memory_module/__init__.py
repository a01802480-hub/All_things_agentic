"""
Memory_module — independent memory subsystem for higher-level agents.

Import the whole thing from here in the parent process:

    from Memory_module import MemoryManager, get_memory_manager

See README.md for the full API reference and integration guide.
"""

from .long_memory import LocalJsonStore, VectorStore
from .memory_logic import MemoryConfig, MemoryManager, get_memory_manager
from .short_memory import ChatMessage, SessionState, ShortTermMemory

__all__ = [
    "MemoryManager",
    "MemoryConfig",
    "get_memory_manager",
    "ShortTermMemory",
    "ChatMessage",
    "SessionState",
    "VectorStore",
    "LocalJsonStore",
]

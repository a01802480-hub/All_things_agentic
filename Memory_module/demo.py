"""
demo.py — end-to-end demo against the real Pinecone backend.

Run from the repository root:

    python -m Memory_module.demo

What it does:
  1. Connects (creating the index on first run, which can take ~1 minute).
  2. Saves a couple of explicit preferences.
  3. Feeds a conversation turn through the triage pipeline.
  4. Shows the stored profile and a context retrieval for the next LLM call.
"""

from .memory_logic import MemoryManager


def main() -> None:
    print("Initializing MemoryManager (first run may create the index)...")
    manager = MemoryManager()

    user_id = "demo_user"
    session_id = "demo_session"

    print("\n[health] ", manager.health_check())

    # 1) Explicit long-term saves (bypass triage)
    manager.save_user_preference(user_id, "food", "Loves Italian food, especially homemade pasta")
    manager.save_user_preference(user_id, "work", "Works as a data engineer and prefers Python for everything")

    # 2) A normal turn: the triage pipeline should extract the durable facts
    print("\n[process_user_input]")
    print(manager.process_user_input(session_id, user_id, "By the way, my name is Santiago and I love reading sci-fi."))
    manager.add_assistant_reply(session_id, "Nice to meet you, Santiago! Sci-fi is great.")

    # 3) What long-term memory now holds for this user (compact JSON mirror)
    print("\n[get_user_profile]")
    for note in manager.get_user_profile(user_id):
        print(f"  - {note['topic']}: {note['content']}")

    # 4) Context assembly for the next LLM call
    print("\n[build_agent_prompt]")
    print(manager.build_agent_prompt(session_id, user_id, "Can you recommend dinner ideas?"))

    # Cleanup (uncomment to wipe the demo data):
    # manager.delete_user_memory(user_id)
    # manager.clear_session(session_id)


if __name__ == "__main__":
    main()

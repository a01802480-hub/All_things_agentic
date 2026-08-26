import tempfile
import unittest
from pathlib import Path

from Memory_module import MemoryConfig, MemoryManager


class MemoryModuleSmokeTest(unittest.TestCase):
    def test_public_workflow_without_pinecone(self) -> None:
        with tempfile.TemporaryDirectory() as data_dir:
            manager = MemoryManager(MemoryConfig(data_dir=data_dir, use_pinecone=False))

            result = manager.process_user_input("session", "user", "My name is Alex and I love sci-fi.")
            manager.add_assistant_reply("session", "Nice to meet you, Alex!")
            prompt = manager.build_agent_prompt("session", "user", "Recommend a book")

            self.assertEqual(result["triage_topic"], "name")
            self.assertEqual(len(manager.get_user_profile("user")), 1)
            self.assertEqual([item["role"] for item in prompt["history"]], ["user", "assistant"])
            self.assertIn("Alex", prompt["user_profile"])
            self.assertEqual(manager.health_check()["backend"], "local")
            self.assertTrue(Path(data_dir, "user.json").exists())


if __name__ == "__main__":
    unittest.main()

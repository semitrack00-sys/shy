"""Exercise the real chat history loader in the full runtime release gate."""
import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "services/core"))


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "Full runtime and disposable database are required")
class ChatContextLimits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        cls.core = main

    def run_loader(self, selected, fallback, durable):
        core = self.core
        with patch.object(core, "retrieve_memory_context", return_value=SimpleNamespace(selected_messages=selected)), \
             patch.object(core, "retrieve_durable_memory_context", return_value=SimpleNamespace(selected_messages=durable)), \
             patch.object(core, "load_messages", return_value=fallback):
            return core._load_memory_history_for_message("Recall project database", uuid.uuid4())

    def test_fallback_and_durable_context_obey_combined_hard_budget(self):
        history, used = self.run_loader([], [{"role": "user", "content": "a" * 100_000}],
                                       [{"role": "assistant", "content": "b" * 50_000}])
        self.assertTrue(used)
        self.assertEqual(sum(len(item["content"]) for item in history), 4400)
        self.assertTrue(all(item["content"].startswith("[Context excerpt truncated]") for item in history))

    def test_selector_oversize_is_capped_and_empty_context_is_not_claimed_used(self):
        history, used = self.run_loader([{"role": "assistant", "content": "x" * 50_000}], [], [])
        self.assertTrue(used)
        self.assertEqual(sum(len(item["content"]) for item in history), 3200)
        history, used = self.run_loader([], [], [])
        self.assertEqual(history, [])
        self.assertFalse(used)


if __name__ == "__main__":
    unittest.main()

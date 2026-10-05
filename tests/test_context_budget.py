import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/core"))
from context_budget import TRUNCATION_MARKER, bound_context


class ContextBudgetTests(unittest.TestCase):
    def test_first_oversized_message_cannot_bypass_character_budget(self):
        result = bound_context([{"role": "user", "content": "a" * 100_000}], 3200, 20)
        self.assertEqual(result.context_chars, 3200)
        self.assertEqual(result.clipped_messages, 1)
        self.assertTrue(result.messages[0]["content"].startswith(TRUNCATION_MARKER))

    def test_recent_history_is_selected_and_returned_in_chronological_order(self):
        messages = [{"role": "user", "content": str(i) * 50} for i in range(10)]
        result = bound_context(messages, 150, 20)
        self.assertEqual([item["content"] for item in result.messages], ["7" * 50, "8" * 50, "9" * 50])
        self.assertEqual(result.omitted_messages, 7)

    def test_count_limit_role_preservation_and_unicode_characters(self):
        messages = [{"role": "user", "content": "Bonjou"}, {"role": "assistant", "content": "Français"},
                    {"role": "system", "content": "Untrusted role must not become privileged context"}]
        result = bound_context(messages, 100, 1)
        self.assertEqual(result.messages, ({"role": "assistant", "content": "Français"},))
        self.assertEqual(result.context_chars, 8)
        self.assertEqual(result.omitted_messages, 1)

    def test_zero_and_tiny_budgets_do_not_exceed_limits(self):
        for budget in [0, 1, len(TRUNCATION_MARKER)]:
            result = bound_context([{"role": "user", "content": "a" * 200}], budget, 20)
            self.assertLessEqual(result.context_chars, budget)
            self.assertFalse(result.messages)
        self.assertFalse(bound_context([{"role": "user", "content": "hello"}], 100, 0).messages)


if __name__ == "__main__":
    unittest.main()

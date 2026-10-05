import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("speech_evaluation", ROOT / "scripts/evaluate_speech.py")
evaluation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evaluation
spec.loader.exec_module(evaluation)


class SpeechMetricTests(unittest.TestCase):
    def test_word_errors_count_substitution_insertion_and_deletion(self):
        self.assertEqual(evaluation.edit_distance(["hello", "world"], ["hello", "SHY"]), 1)
        self.assertEqual(evaluation.edit_distance(["hello"], ["hello", "world"]), 1)
        self.assertEqual(evaluation.edit_distance(["hello", "world"], ["hello"]), 1)
        self.assertEqual(evaluation.edit_distance(["hello"], []), 1)

    def test_accented_words_are_preserved_and_typographic_apostrophes_normalized(self):
        self.assertEqual(evaluation.words("Bonjou, fanmi!"), ["bonjou", "fanmi"])
        self.assertEqual(evaluation.words("L’école"), ["l'école"])
        self.assertNotEqual(evaluation.words("créole"), evaluation.words("creole"))


if __name__ == "__main__":
    unittest.main()

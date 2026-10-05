import importlib.util
import os
import sys
import unittest
from unittest.mock import patch
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

    def test_failed_requests_do_not_claim_acoustic_inference_or_passing_quality(self):
        import base64
        import io
        import wave
        output = io.BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * 160)
        cases = [("en-01", "en", ["reference"], base64.b64encode(output.getvalue()).decode(), 0.01, "digest")]
        async def unavailable(*args):
            raise evaluation.voice_api.HTTPException(503, "local_speech_provider_unavailable_or_timed_out")
        with patch.dict(os.environ, {"SHY_WHISPER_URL": "http://127.0.0.1:8178"}), \
                patch.object(evaluation.voice_api, "transcribe_provider", unavailable):
            report = evaluation.evaluate_cases(cases, 0.25, 3)
        self.assertFalse(report["passed"])
        self.assertFalse(report["real_audio_inference"])
        self.assertEqual(report["inference_requests_attempted"], 1)
        self.assertIsNone(report["languages"]["en"]["corpus_wer"])
        self.assertFalse(report["languages"]["ht"]["coverage_complete"])


if __name__ == "__main__":
    unittest.main()

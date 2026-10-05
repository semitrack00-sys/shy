import importlib.util
import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("speech_import", ROOT / "scripts/import_speech_corpus.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SpeechImportTests(unittest.TestCase):
    def make_dataset(self, root, language, offset=0, frames=160):
        directory = root / language
        (directory / "clips").mkdir(parents=True)
        rows = ["path\tsentence"]
        for index in range(3):
            name = f"clip-{index}.wav"
            with wave.open(str(directory / "clips" / name), "wb") as audio:
                audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                audio.writeframes(int(offset + index + 1).to_bytes(2, "little") * frames)
            rows.append(f"{name}\tReference words {index}")
        (directory / "test.tsv").write_text("\n".join(rows), encoding="utf-8")
        return directory

    def test_path_traversal_and_insufficient_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.make_dataset(root, "en")
            with self.assertRaises(ValueError):
                module.read_split(directory, 4)
            (directory / "test.tsv").write_text("path\tsentence\n../private.wav\tReference words\n")
            with self.assertRaises(ValueError):
                module.read_split(directory, 3)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required for real format conversion")
    def test_complete_conversion_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            datasets = {language: self.make_dataset(root, language, index * 10)
                        for index, language in enumerate(sorted(module.LANGUAGES))}
            output = root / "evaluation"
            self.assertEqual(module.import_corpus(datasets, output, 3, shutil.which("ffmpeg")), 9)
            cases = json.loads((output / "cases.json").read_text())["cases"]
            self.assertEqual({case["language"] for case in cases}, module.LANGUAGES)
            self.assertEqual(len(list(output.glob("*.wav"))), 9)
            self.assertEqual((output / "en-01.wav").stat().st_size, 44 + 160 * 2)
            with self.assertRaises(ValueError):
                module.import_corpus(datasets, output, 3, shutil.which("ffmpeg"))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required for real format conversion")
    def test_duplicate_and_long_audio_leave_no_partial_corpus(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            datasets = {language: self.make_dataset(root, language) for language in module.LANGUAGES}
            output = root / "evaluation"
            with self.assertRaises(ValueError):
                module.import_corpus(datasets, output, 3, shutil.which("ffmpeg"))
            self.assertFalse(output.exists())
            self.assertFalse(list(root.glob(".shy-speech-*")))
            source = root / "long.wav"
            with wave.open(str(source), "wb") as audio:
                audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                audio.writeframes(b"\0\0" * 496000)
            with self.assertRaises(ValueError):
                module.convert_audio(source, root / "converted.wav", shutil.which("ffmpeg"))


if __name__ == "__main__":
    unittest.main()

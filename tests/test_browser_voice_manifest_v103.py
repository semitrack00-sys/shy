"""The core describes browser-dependent voice without claiming an audio provider."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("voice_manifest_v103", ROOT / "services/agent-runtime/platform_manifest.py")
manifest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manifest
spec.loader.exec_module(manifest)


class VoiceManifestTests(unittest.TestCase):
    def test_current_voice_sequence_and_core_audio_boundary(self):
        current = manifest.build_platform_manifest(version="0.103.0")
        self.assertEqual(current.version, "0.103.0")
        self.assertTrue(current.sequence_complete)
        self.assertTrue(current.required_disabled_invariants_hold)
        by_id = {item.capability_id: item for item in current.capabilities}
        self.assertEqual(by_id["browser_voice_chat"].introduced_version, "0.101.0")
        self.assertEqual(by_id["voice_interruption"].introduced_version, "0.102.0")
        self.assertEqual(by_id["voice_silence_handling"].introduced_version, "0.103.0")
        self.assertEqual(by_id["raw_audio_capture"].state, manifest.CapabilityState.DISABLED)

    def test_historical_releases_do_not_claim_browser_voice(self):
        old = manifest.build_platform_manifest(version="0.100.0")
        self.assertTrue(old.sequence_complete)
        self.assertFalse(any(item.capability_id == "browser_voice_chat" for item in old.capabilities))


if __name__ == "__main__":
    unittest.main()

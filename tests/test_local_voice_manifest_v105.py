import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_voice_manifest_v105", ROOT / "services/agent-runtime/platform_manifest.py")
manifest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manifest
spec.loader.exec_module(manifest)


class LocalVoiceManifestTests(unittest.TestCase):
    def test_current_local_input_and_output_controls_are_bounded(self):
        current = manifest.build_platform_manifest(version="0.105.0")
        self.assertEqual(current.version, "0.105.0")
        self.assertTrue(current.sequence_complete)
        self.assertTrue(current.required_disabled_invariants_hold)
        by_id = {item.capability_id: item for item in current.capabilities}
        self.assertEqual(by_id["local_microphone_input"].introduced_version, "0.104.0")
        self.assertEqual(by_id["voice_output_controls"].introduced_version, "0.105.0")
        self.assertEqual(by_id["local_microphone_input"].state, manifest.CapabilityState.BOUNDED)
        self.assertNotIn("wake_word", by_id)

    def test_old_release_does_not_advertise_future_provider_adapter(self):
        old = manifest.build_platform_manifest(version="0.103.0")
        self.assertTrue(old.sequence_complete)
        self.assertFalse(any(item.capability_id == "local_microphone_input" for item in old.capabilities))


if __name__ == "__main__":
    unittest.main()

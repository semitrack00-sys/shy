import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("memory_controls_manifest", ROOT / "services/agent-runtime/platform_manifest.py")
manifest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manifest
spec.loader.exec_module(manifest)


class MemoryManifestTests(unittest.TestCase):
    def test_current_patch_retains_disabled_invariants_and_bounded_controls(self):
        current = manifest.build_platform_manifest(version="0.105.1")
        self.assertEqual(current.version, "0.105.1")
        self.assertTrue(current.sequence_complete)
        self.assertTrue(current.required_disabled_invariants_hold)
        by_id = {cap.capability_id: cap for cap in current.capabilities}
        self.assertEqual(by_id["reviewed_memory_controls"].state, manifest.CapabilityState.BOUNDED)
        self.assertEqual(by_id["conversation_summary"].state, manifest.CapabilityState.BOUNDED)
        old = manifest.build_platform_manifest(version="0.105.0")
        self.assertFalse(any(cap.capability_id == "reviewed_memory_controls" for cap in old.capabilities))


if __name__ == "__main__":
    unittest.main()

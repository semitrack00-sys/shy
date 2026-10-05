import importlib.util
import sys
import unittest
from intelligence_helpers import ROOT
from intelligence.common import validate_payload
from intelligence.registry import CAPABILITIES, catalog, evaluate


spec = importlib.util.spec_from_file_location("manifest_v100", ROOT / "services" / "agent-runtime" / "platform_manifest.py")
manifest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = manifest
spec.loader.exec_module(manifest)


class RegistryTests(unittest.TestCase):
    def test_fifty_real_handlers_match_manifest_and_versions(self):
        self.assertEqual([x[0] for x in CAPABILITIES], list(range(51, 101)))
        self.assertEqual(len({x[1] for x in CAPABILITIES}), 50)
        current = manifest.build_platform_manifest(version="0.100.0")
        self.assertEqual(current.version, "0.100.0")
        self.assertTrue(current.sequence_complete)
        self.assertTrue(current.required_disabled_invariants_hold)
        by_id = {x.capability_id: x for x in current.capabilities}
        for version, name, handler in CAPABILITIES:
            self.assertTrue(callable(handler))
            self.assertEqual(by_id[name].introduced_version, f"0.{version}.0")
        self.assertEqual(len(catalog()), 50)

    def test_historical_manifest_does_not_advertise_future_capabilities(self):
        old = manifest.build_platform_manifest(version="0.50.0")
        self.assertTrue(old.sequence_complete)
        self.assertFalse(any(x.capability_id == "evidence_pipeline" for x in old.capabilities))
        self.assertTrue(manifest.build_platform_manifest(version="0.30.0").sequence_complete)

    def test_missing_handler_version_blocks_sequence(self):
        current = manifest.build_platform_manifest()
        missing = tuple(x for x in current.capabilities if x.introduced_version != "0.97.0")
        self.assertFalse(manifest.build_platform_manifest(capabilities=missing).sequence_complete)

    def test_each_handler_rejects_missing_input(self):
        for _, name, _ in CAPABILITIES:
            with self.subTest(capability=name):
                self.assertEqual(evaluate(name, {})["boundary"], "INPUT_REQUIRED")

    def test_unknown_and_nonobject_inputs_fail_closed(self):
        self.assertEqual(evaluate("shell", {})["boundary"], "UNAVAILABLE")
        self.assertEqual(evaluate("chunk_text", [1])["boundary"], "INPUT_REQUIRED")

    def test_payload_limits_nonfinite_and_boolean_numeric(self):
        for payload in [{"text": "x" * 16001}, {"values": [1] * 501}, {"values": [float("nan")]}, {"values": [float("inf")]}, {"values": [True]}]:
            self.assertEqual(evaluate("descriptive_stats", payload)["boundary"], "INPUT_REQUIRED")
        value = "leaf"
        for _ in range(14):
            value = [value]
        self.assertEqual(evaluate("descriptive_stats", {"values": value})["boundary"], "INPUT_REQUIRED")

    def test_aggregate_byte_limit(self):
        p = {"text": ["a" * 15000] * 20}
        with self.assertRaises(ValueError):
            validate_payload(p)

    def test_malformed_enums_return_input_boundary(self):
        for value in [None, [], {}, True, 7]:
            self.assertEqual(evaluate("join_rows", {"left": [{"id": 1}], "right": [{"id": 1}], "keys": ["id"], "mode": value})["boundary"], "INPUT_REQUIRED")
            self.assertEqual(evaluate("regression_report", {"metrics": [{"id": "x", "baseline": 1, "current": 2, "direction": value}]})["boundary"], "INPUT_REQUIRED")

    def test_numerical_overflow_rejected(self):
        self.assertEqual(evaluate("capacity_estimate", {"requests_per_second": 1e308, "service_time_seconds": 1e308, "slots_per_instance": 1})["boundary"], "INPUT_REQUIRED")
        self.assertEqual(evaluate("transform_rows", {"rows": [{"x": 1e308}], "transforms": [{"column": "x", "operation": "scale", "factor": 1e308}]})["boundary"], "INPUT_REQUIRED")

    def test_evaluation_is_deterministic_and_does_not_mutate_input(self):
        import copy
        p = {"rows": [{"x": 1}], "transforms": [{"column": "x", "operation": "scale", "factor": 3}]}
        before = copy.deepcopy(p)
        first = evaluate("transform_rows", p)
        self.assertEqual(first, evaluate("transform_rows", p))
        self.assertEqual(p, before)
        self.assertFalse(first["side_effect_performed"])
        self.assertFalse(first["result_is_authorization"])


if __name__ == "__main__":
    unittest.main()

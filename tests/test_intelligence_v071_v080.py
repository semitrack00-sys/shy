import unittest
from intelligence_helpers import rejects
from intelligence import data as d


class DataTests(unittest.TestCase):
    def test_071_schema_distinguishes_bool_and_number(self):
        result = d.profile_schema({"rows": [{"x": True}, {"x": 1}, {}]})
        self.assertEqual(result["columns"][0]["types"], {"boolean": 1, "number": 1, "null": 1})
        self.assertTrue(result["columns"][0]["mixed_non_null_types"])

    def test_072_known_population_statistics(self):
        result = d.descriptive_stats({"values": [1, 2, 3, 4]})
        self.assertEqual(result["mean"], 2.5)
        self.assertEqual(result["median"], 2.5)
        self.assertEqual(result["q1"], 1.75)
        rejects(d.descriptive_stats, {"values": [True, 2]})

    def test_073_robust_outlier_and_constant_series(self):
        self.assertEqual(d.detect_outliers({"values": [2, 2, 2, 100]})["indices"], [3])
        self.assertEqual(d.detect_outliers({"values": [2, 2, 2]})["indices"], [])
        rejects(d.detect_outliers, {"values": [1], "threshold": 0})

    def test_074_missing_values_do_not_include_zero_or_false(self):
        result = d.missing_report({"rows": [{"x": 0}, {"x": False}, {"x": None}, {}]})
        self.assertEqual(result["columns"][0]["row_indices"], [2, 3])

    def test_075_deduplication_surfaces_conflicting_duplicates(self):
        result = d.deduplicate_rows({"rows": [{"id": 1, "v": 2}, {"id": 1, "v": 3}], "keys": ["id"]})
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["conflicts"], [{"kept_index": 0, "duplicate_index": 1}])
        rejects(d.deduplicate_rows, {"rows": [{"x": 1}], "keys": ["id"]})

    def test_076_left_join_preserves_colliding_fields_and_unmatched_rows(self):
        result = d.join_rows({"left": [{"id": 1, "v": "left"}, {"id": 2}], "right": [{"id": 1, "v": "right"}], "keys": ["id"], "mode": "left"})
        self.assertEqual(result["rows"][0]["left"]["v"], "left")
        self.assertEqual(result["rows"][0]["right"]["v"], "right")
        self.assertIsNone(result["rows"][1]["right"])
        rejects(d.join_rows, {"left": [{"id": 1}] * 30, "right": [{"id": 1}] * 30, "keys": ["id"]})

    def test_077_grouped_numeric_aggregation(self):
        result = d.aggregate_rows({"rows": [{"country": "HT", "usd": 5}, {"country": "HT", "usd": 10}], "group_by": ["country"], "value_column": "usd"})
        self.assertEqual(result["groups"][0]["sum"], 15)
        self.assertEqual(result["groups"][0]["mean"], 7.5)

    def test_078_transform_allowlist_without_mutating_input(self):
        items = [{"price": 2, "name": "shy"}]
        result = d.transform_rows({"rows": items, "transforms": [{"column": "price", "operation": "scale", "factor": 3}, {"column": "name", "operation": "uppercase"}]})
        self.assertEqual(result["rows"], [{"price": 6, "name": "SHY"}])
        self.assertEqual(items[0]["price"], 2)
        rejects(d.transform_rows, {"rows": items, "transforms": [{"column": "price", "operation": "eval"}]})

    def test_079_snapshot_diff_reports_add_remove_change(self):
        result = d.compare_snapshots({"before": [{"id": 1, "v": 2}, {"id": 2}], "after": [{"id": 1, "v": 3}, {"id": 3}], "keys": ["id"]})
        self.assertEqual(result["added"], [{"id": 3}])
        self.assertEqual(result["removed"], [{"id": 2}])
        self.assertEqual(len(result["changed"]), 1)
        rejects(d.compare_snapshots, {"before": [{"id": 1}, {"id": 1}], "after": [], "keys": ["id"]})

    def test_080_quality_enforces_range_unique_and_required(self):
        result = d.data_quality({"rows": [{"id": 1, "v": 5}, {"id": 1, "v": 101}], "rules": [{"column": "id", "check": "unique"}, {"column": "v", "check": "numeric_range", "min": 5, "max": 100}, {"column": "name", "check": "required"}]})
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["failures"]), 4)
        rejects(d.data_quality, {"rows": [{"v": 1}], "rules": [{"column": "v", "check": "numeric_range", "min": 2, "max": 1}]})


if __name__ == "__main__":
    unittest.main()

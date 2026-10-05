import unittest
from intelligence_helpers import rejects
from intelligence import workflows as w
from intelligence.common import digest

TASKS = [{"id": "a", "duration": 2}, {"id": "b", "duration": 3, "dependencies": ["a"]}, {"id": "c", "duration": 1, "dependencies": ["a"]}]


class WorkflowTests(unittest.TestCase):
    def test_061_dependency_schedule_and_cycle_rejection(self):
        result = w.schedule_tasks({"tasks": TASKS})
        self.assertEqual(result["makespan"], 5)
        self.assertEqual(result["schedule"][1]["start"], 2)
        rejects(w.schedule_tasks, {"tasks": [{"id": "a", "dependencies": ["a"]}]})
        rejects(w.schedule_tasks, {"tasks": [{"id": "a", "dependencies": ["missing"]}]})

    def test_062_slack_calculation(self):
        result = w.critical_path({"tasks": TASKS})
        self.assertEqual({x["id"]: x["slack"] for x in result["tasks"]}, {"a": 0, "b": 0, "c": 2})

    def test_063_checkpoint_tamper_detection(self):
        p = {"checkpoint": {"state": "ready"}, "sha256": digest({"state": "ready"})}
        self.assertTrue(w.verify_checkpoint(p)["integrity_matches"])
        self.assertFalse(w.verify_checkpoint({**p, "checkpoint": {"state": "changed"}})["integrity_matches"])

    def test_064_retry_requires_idempotency_and_honors_retry_after(self):
        p = {"failure": "timeout", "idempotent": True, "attempt": 1, "retry_after": 80}
        self.assertEqual(w.retry_policy(p)["delay_seconds"], 80)
        self.assertFalse(w.retry_policy({**p, "idempotent": False})["retry"])
        self.assertFalse(w.retry_policy({**p, "attempt": 3})["retry"])
        self.assertFalse(w.retry_policy({**p, "failure": "invalid_input"})["retry"])

    def test_065_fingerprint_canonical_and_scope_bound(self):
        p = {"scope": "a", "operation": "read", "arguments": {"x": 1, "y": 2}}
        first = w.idempotency_fingerprint(p)["fingerprint"]
        self.assertEqual(first, w.idempotency_fingerprint({**p, "arguments": {"y": 2, "x": 1}})["fingerprint"])
        self.assertNotEqual(first, w.idempotency_fingerprint({**p, "scope": "b"})["fingerprint"])

    def test_066_budget_minimum_and_weight_distribution(self):
        p = {"total": 10, "tasks": [{"id": "a", "minimum": 2, "weight": 1}, {"id": "b", "minimum": 2, "weight": 2}]}
        self.assertEqual([x["amount"] for x in w.allocate_budget(p)["allocations"]], [4, 6])
        self.assertFalse(w.allocate_budget({**p, "total": 3})["feasible"])

    def test_067_cancellation_only_descendants(self):
        result = w.cancellation_plan({"tasks": TASKS, "target": "b"})
        self.assertEqual(result["affected_ids"], ["b"])
        self.assertEqual(result["unaffected_ids"], ["a", "c"])

    def test_068_approval_is_bound_but_never_authenticated_here(self):
        request = {"tool": "send", "recipient": "a"}
        p = {"request": request, "now": "2026-10-05T00:00:00Z", "approval": {"request_sha256": digest(request), "expires_at": "2026-10-05T00:01:00Z"}}
        self.assertTrue(w.approval_binding(p)["eligible_for_gateway_verification"])
        self.assertFalse(w.approval_binding(p)["authorization_granted"])
        self.assertFalse(w.approval_binding({**p, "request": {"tool": "send", "recipient": "b"}})["request_matches"])

    def test_069_recovery_preserves_completed_and_flags_unsafe_replay(self):
        tasks = [*TASKS[:1], {**TASKS[1], "side_effects": True}]
        result = w.recovery_plan({"tasks": tasks, "completed": ["a"], "failed": ["b"]})
        self.assertEqual(result["resume_ids"], ["b"])
        self.assertEqual(result["requires_gateway_review"], ["b"])
        rejects(w.recovery_plan, {"tasks": TASKS, "completed": ["b"]})

    def test_070_dry_run_denies_unknown_and_reviews_side_effects(self):
        result = w.dry_run({"actions": [{"id": "1", "operation": "send", "side_effects": True}, {"id": "2", "operation": "shell", "side_effects": True}], "allowed_operations": ["send"]})
        self.assertEqual([x["decision"] for x in result["actions"]], ["review_required", "denied"])
        self.assertFalse(result["execution_performed"])
        rejects(w.dry_run, {"actions": [{"id": "1", "operation": "send", "side_effects": "false"}]})


if __name__ == "__main__":
    unittest.main()

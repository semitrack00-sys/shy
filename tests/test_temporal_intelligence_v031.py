import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"temporal_intelligence.py"
spec=importlib.util.spec_from_file_location("shy_temporal_v031",P)
temporal=importlib.util.module_from_spec(spec)
sys.modules["shy_temporal_v031"]=temporal
spec.loader.exec_module(temporal)

def a(c,m):
    if not c: raise AssertionError(m)

tasks=(
    temporal.TemporalTask("load",30,"2026-10-05T08:00:00-07:00","2026-10-05T09:00:00-07:00"),
    temporal.TemporalTask("deliver",60,"2026-10-05T08:15:00-07:00","2026-10-05T11:00:00-07:00",("load",)),
)
plan=temporal.plan_temporal_tasks(tasks)
a(plan.boundary==temporal.TemporalBoundary.READY,plan)
a(plan.tasks[1].start=="2026-10-05T08:30:00-07:00",plan.tasks[1])
a(plan.external_schedule_created is False,"planner must not create external schedule")
print("dependency-aware temporal plan: PASS")

naive=temporal.plan_temporal_tasks((
    temporal.TemporalTask("x",30,"2026-10-05T08:00:00","2026-10-05T09:00:00"),
))
a(naive.boundary==temporal.TemporalBoundary.TIMEZONE_REQUIRED,naive)
print("timezone-aware requirement: PASS")

cycle=temporal.plan_temporal_tasks((
    temporal.TemporalTask("a",10,"2026-10-05T08:00:00+00:00","2026-10-05T10:00:00+00:00",("b",)),
    temporal.TemporalTask("b",10,"2026-10-05T08:00:00+00:00","2026-10-05T10:00:00+00:00",("a",)),
))
a(cycle.boundary==temporal.TemporalBoundary.CYCLE_DETECTED,cycle)
print("dependency cycle detection: PASS")

conflict=temporal.plan_temporal_tasks((
    temporal.TemporalTask("late",90,"2026-10-05T08:00:00+00:00","2026-10-05T09:00:00+00:00"),
))
a(conflict.boundary==temporal.TemporalBoundary.DEADLINE_CONFLICT,conflict)
a(conflict.conflict_task_ids==("late",),conflict)
print("deadline conflict detection: PASS")

preview=temporal.preview_recurrence("2026-10-05T08:00:00+00:00",every_minutes=60,occurrences=30,max_occurrences=20)
a(len(preview.occurrences)==20,preview)
a(preview.bounded is False,preview)
a(preview.external_schedule_created is False,"preview must not schedule")
print("bounded recurrence preview: PASS")

print("SHY v0.31 TEMPORAL INTELLIGENCE: PASS")

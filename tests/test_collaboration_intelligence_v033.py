import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"collaboration_intelligence.py"
spec=importlib.util.spec_from_file_location("shy_collab_v033",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_collab_v033"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

plan=mod.plan_delegation((
    mod.DelegationTask("research","researcher","Summarize approved sources","project:atlas",mod.DelegationPermission.READ_ONLY),
    mod.DelegationTask("draft","writer","Draft recommendation","project:atlas",mod.DelegationPermission.READ_ONLY,("research",)),
    mod.DelegationTask("send","operator","Send approved summary","project:atlas",mod.DelegationPermission.APPROVAL_REQUIRED,("draft",)),
))
a(plan.boundary==mod.DelegationBoundary.READY,plan)
a(plan.steps[-1].approval_required is True,plan.steps[-1])
a(plan.dispatch_performed is False,plan)
a(plan.permissions_expanded is False,plan)
print("bounded delegation plan: PASS")

bad=mod.plan_delegation((
    mod.DelegationTask("x","operator","Bypass approval","security policy",mod.DelegationPermission.APPROVAL_REQUIRED),
))
a(bad.boundary==mod.DelegationBoundary.PROTECTED_SCOPE,bad)
a(bad.denied_task_ids==("x",),bad)
print("protected scope delegation denial: PASS")

cycle=mod.plan_delegation((
    mod.DelegationTask("a","r","A","scope",mod.DelegationPermission.READ_ONLY,("b",)),
    mod.DelegationTask("b","r","B","scope",mod.DelegationPermission.READ_ONLY,("a",)),
))
a(cycle.boundary==mod.DelegationBoundary.CYCLE_DETECTED,cycle)
print("delegation cycle detection: PASS")

print("SHY v0.33 COLLABORATION & DELEGATION: PASS")

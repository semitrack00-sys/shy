import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v034",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v034"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

ready=mod.evaluate_advanced_capability("recovery_rollback",{
    "target_checkpoint":"cp-2",
    "target_resource":"service:api",
    "objective":"restore last known good application state",
    "checkpoints":[
        {"checkpoint_id":"cp-1","verified":True},
        {"checkpoint_id":"cp-2","verified":True},
    ],
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.side_effect_performed is False,ready)
a(ready.payload["execution_allowed_here"] is False,ready.payload)
print("verified rollback planning: PASS")

unverified=mod.evaluate_advanced_capability("recovery_rollback",{
    "target_checkpoint":"cp-x",
    "checkpoints":[{"checkpoint_id":"cp-x","verified":False}],
})
a(unverified.boundary==mod.AdvancedBoundary.CONFLICT,unverified)
a(unverified.reason=="verified_checkpoint_required",unverified.reason)
print("unverified checkpoint blocked: PASS")

protected=mod.evaluate_advanced_capability("recovery_rollback",{
    "target_checkpoint":"cp-1",
    "target_resource":"security policy",
    "checkpoints":[{"checkpoint_id":"cp-1","verified":True}],
})
a(protected.boundary==mod.AdvancedBoundary.PROTECTED_TARGET,protected)
print("protected rollback target blocked: PASS")

unsupported=mod.evaluate_advanced_capability("unknown",{})
a(unsupported.boundary==mod.AdvancedBoundary.INVALID_INPUT,unsupported)
print("unsupported advanced capability boundary: PASS")

print("SHY v0.34 RECOVERY & ROLLBACK INTELLIGENCE: PASS")

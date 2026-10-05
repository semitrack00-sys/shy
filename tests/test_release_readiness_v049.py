import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v049",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v049"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

ready=mod.evaluate_advanced_capability("release_readiness",{
    "checks":[
        {"check_id":"tests","category":"quality","required":True,"passed":True,"verified":True},
        {"check_id":"security","category":"security","required":True,"passed":True,"verified":True},
        {"check_id":"docs","category":"docs","required":False,"passed":False,"verified":False},
    ]
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.payload["release_ready"] is True,ready.payload)
a(ready.payload["deployment_executed"] is False,ready.payload)
a(ready.payload["merge_executed"] is False,ready.payload)
print("verified release readiness: PASS")

blocked=mod.evaluate_advanced_capability("release_readiness",{
    "checks":[
        {"check_id":"tests","required":True,"passed":False,"verified":True},
    ]
})
a(blocked.boundary==mod.AdvancedBoundary.CONFLICT,blocked)
a(blocked.payload["release_ready"] is False,blocked.payload)
print("failed required check blocks release: PASS")

unverified=mod.evaluate_advanced_capability("release_readiness",{
    "checks":[
        {"check_id":"security","required":True,"passed":True,"verified":False},
    ]
})
a(unverified.boundary==mod.AdvancedBoundary.DATA_REQUIRED,unverified)
print("unverified required check boundary: PASS")

print("SHY v0.49 RELEASE READINESS INTELLIGENCE: PASS")

import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v041",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v041"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

ready=mod.evaluate_advanced_capability("compliance_policy",{
    "evidence_ids":["e1","e2"],
    "requirements":[
        {"requirement_id":"r1","mandatory":True,"required_evidence_ids":["e1"]},
        {"requirement_id":"r2","mandatory":False,"required_evidence_ids":["e2"]},
    ],
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.payload["certification_issued"] is False,ready.payload)
a(ready.payload["policy_changed"] is False,ready.payload)
print("complete compliance evidence review: PASS")

missing=mod.evaluate_advanced_capability("compliance_policy",{
    "evidence_ids":["e1"],
    "requirements":[
        {"requirement_id":"r1","mandatory":True,"required_evidence_ids":["e1","e2"]},
    ],
})
a(missing.boundary==mod.AdvancedBoundary.DATA_REQUIRED,missing)
a(missing.payload["mandatory_missing"]==["r1"],missing.payload)
print("mandatory evidence gap: PASS")

dup=mod.evaluate_advanced_capability("compliance_policy",{
    "requirements":[
        {"requirement_id":"r1","required_evidence_ids":[]},
        {"requirement_id":"r1","required_evidence_ids":[]},
    ],
})
a(dup.boundary==mod.AdvancedBoundary.INVALID_INPUT,dup)
print("duplicate requirement rejection: PASS")

print("SHY v0.41 COMPLIANCE & POLICY INTELLIGENCE: PASS")

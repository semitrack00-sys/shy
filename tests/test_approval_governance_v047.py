import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v047",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v047"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

ready=mod.evaluate_advanced_capability("approval_governance",{
    "required_approvals":2,
    "allowed_roles":["owner","admin"],
    "approvals":[
        {"actor_id":"u1","role":"owner","approved":True,"verified":True},
        {"actor_id":"u2","role":"admin","approved":True,"verified":True},
        {"actor_id":"u3","role":"viewer","approved":True,"verified":True},
    ],
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.payload["quorum_met"] is True,ready.payload)
a(ready.payload["verified_approval_count"]==2,ready.payload)
a(ready.payload["approval_token_issued"] is False,ready.payload)
a(ready.payload["action_executed"] is False,ready.payload)
print("verified human approval quorum: PASS")

missing=mod.evaluate_advanced_capability("approval_governance",{
    "required_approvals":2,
    "approvals":[
        {"actor_id":"u1","role":"owner","approved":True,"verified":True},
        {"actor_id":"u2","role":"admin","approved":True,"verified":False},
    ],
})
a(missing.boundary==mod.AdvancedBoundary.DATA_REQUIRED,missing)
a(missing.payload["quorum_met"] is False,missing.payload)
print("unverified approval does not count: PASS")

dup=mod.evaluate_advanced_capability("approval_governance",{
    "approvals":[
        {"actor_id":"u1","role":"owner","approved":True,"verified":True},
        {"actor_id":"u1","role":"owner","approved":True,"verified":True},
    ],
})
a(dup.boundary==mod.AdvancedBoundary.INVALID_INPUT,dup)
print("duplicate approver rejection: PASS")

print("SHY v0.47 HUMAN APPROVAL GOVERNANCE: PASS")

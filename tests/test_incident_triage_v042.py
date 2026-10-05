import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v042",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v042"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

result=mod.evaluate_advanced_capability("incident_triage",{
    "incidents":[
        {"incident_id":"i-low","severity":"LOW","confidence":0.9,"affected_units":2},
        {"incident_id":"i-critical","severity":"CRITICAL","confidence":0.8,"affected_units":20},
        {"incident_id":"i-high","severity":"HIGH","confidence":0.95,"affected_units":5},
    ]
})
a(result.boundary==mod.AdvancedBoundary.READY,result)
a(result.payload["priority_order"][0]=="i-critical",result.payload)
a(result.payload["notification_sent"] is False,result.payload)
a(result.payload["remediation_executed"] is False,result.payload)
print("incident priority ranking: PASS")

bad=mod.evaluate_advanced_capability("incident_triage",{
    "incidents":[{"incident_id":"x","severity":"UNKNOWN"}]
})
a(bad.boundary==mod.AdvancedBoundary.INVALID_INPUT,bad)
print("invalid severity rejection: PASS")

print("SHY v0.42 INCIDENT & ANOMALY TRIAGE: PASS")

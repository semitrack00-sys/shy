import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v044",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v044"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

result=mod.evaluate_advanced_capability("change_impact",{
    "components":[
        {"component_id":"db","dependencies":[],"criticality":5},
        {"component_id":"api","dependencies":["db"],"criticality":4},
        {"component_id":"web","dependencies":["api"],"criticality":3},
        {"component_id":"worker","dependencies":["db"],"criticality":2},
    ],
    "changed_component_ids":["db"],
})
a(result.boundary==mod.AdvancedBoundary.READY,result)
a(set(result.payload["impacted_component_ids"])=={"db","api","web","worker"},result.payload)
a(result.payload["risk_level"]=="HIGH",result.payload)
a(result.payload["deployment_executed"] is False,result.payload)
print("dependency blast-radius analysis: PASS")

bad=mod.evaluate_advanced_capability("change_impact",{
    "components":[{"component_id":"api","dependencies":["missing"],"criticality":3}],
    "changed_component_ids":["api"],
})
a(bad.boundary==mod.AdvancedBoundary.INVALID_INPUT,bad)
print("unknown dependency rejection: PASS")

print("SHY v0.44 CHANGE IMPACT INTELLIGENCE: PASS")

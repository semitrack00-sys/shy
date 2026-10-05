import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v043",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v043"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

result=mod.evaluate_advanced_capability("resource_capacity",{
    "resources":[
        {"resource_id":"drivers","capacity":10,"reserve":1,"demand":8},
        {"resource_id":"trucks","capacity":8,"reserve":1,"demand":9},
    ]
})
a(result.boundary==mod.AdvancedBoundary.READY,result)
a("trucks" in result.payload["shortage_resource_ids"],result.payload)
a(result.payload["provisioning_performed"] is False,result.payload)
a(result.payload["hiring_performed"] is False,result.payload)
print("resource shortage analysis: PASS")

bad=mod.evaluate_advanced_capability("resource_capacity",{
    "resources":[{"resource_id":"x","capacity":5,"reserve":6,"demand":1}]
})
a(bad.boundary==mod.AdvancedBoundary.INVALID_INPUT,bad)
print("invalid reserve rejection: PASS")

print("SHY v0.43 RESOURCE & CAPACITY PLANNING: PASS")

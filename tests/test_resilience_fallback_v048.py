import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v048",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v048"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

plan=mod.evaluate_advanced_capability("resilience_fallback",{
    "candidates":[
        {"candidate_id":"primary","priority":1,"healthy":False,"fallback_eligible":True},
        {"candidate_id":"secondary","priority":2,"healthy":True,"fallback_eligible":True},
        {"candidate_id":"tertiary","priority":3,"healthy":True,"fallback_eligible":True},
    ]
})
a(plan.boundary==mod.AdvancedBoundary.READY,plan)
a(plan.payload["selected_primary"]=="secondary",plan.payload)
a(plan.payload["fallback_chain"]==["tertiary"],plan.payload)
a(plan.payload["degraded_input_state"] is True,plan.payload)
a(plan.payload["failover_executed"] is False,plan.payload)
a(plan.payload["traffic_switched"] is False,plan.payload)
print("bounded fallback plan: PASS")

none=mod.evaluate_advanced_capability("resilience_fallback",{
    "candidates":[
        {"candidate_id":"a","priority":1,"healthy":False,"fallback_eligible":True},
    ]
})
a(none.boundary==mod.AdvancedBoundary.DATA_REQUIRED,none)
a(none.payload["failover_executed"] is False,none.payload)
print("no healthy fallback boundary: PASS")

print("SHY v0.48 RESILIENCE & FALLBACK INTELLIGENCE: PASS")

import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v039",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v039"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

ready=mod.evaluate_advanced_capability("business_operations",{
    "kpis":[
        {"name":"on_time_rate","value":0.92,"target":0.95,"weight":2,"direction":"HIGHER"},
        {"name":"damage_rate","value":0.03,"target":0.02,"weight":1,"direction":"LOWER"},
        {"name":"margin","value":0.18,"target":0.20,"weight":2,"direction":"HIGHER"},
    ]
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a("damage_rate" in ready.payload["bottlenecks"],ready.payload)
a(ready.payload["business_action_executed"] is False,ready.payload)
a(ready.payload["pricing_changed"] is False,ready.payload)
a(ready.payload["money_spent"] is False,ready.payload)
print("business KPI assessment: PASS")

invalid=mod.evaluate_advanced_capability("business_operations",{
    "kpis":[{"name":"x","value":1,"target":0,"direction":"HIGHER"}]
})
a(invalid.boundary==mod.AdvancedBoundary.INVALID_INPUT,invalid)
print("business KPI validation: PASS")

many=[{"name":f"k{i}","value":1,"target":1,"direction":"HIGHER"} for i in range(6)]
bounded=mod.evaluate_advanced_capability("business_operations",{"kpis":many,"max_kpis":3})
a(bounded.payload["kpi_count"]==3,bounded.payload)
a(bounded.payload["kpi_limit_enforced"] is False,bounded.payload)
print("business KPI bound: PASS")

print("SHY v0.39 BUSINESS OPERATIONS INTELLIGENCE: PASS")

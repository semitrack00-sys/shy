import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v046",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v046"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

up=mod.evaluate_advanced_capability("forecast_trend",{
    "values":[10,12,14,16,18],
    "horizon":3,
})
a(up.boundary==mod.AdvancedBoundary.READY,up)
a(up.payload["trend_direction"]=="UP",up.payload)
a(up.payload["projected_values"]==[20.0,22.0,24.0],up.payload)
a(up.payload["forecast_guaranteed"] is False,up.payload)
a(up.payload["external_data_fetched"] is False,up.payload)
print("bounded upward projection: PASS")

flat=mod.evaluate_advanced_capability("forecast_trend",{
    "values":[5,5,5],
    "horizon":1,
})
a(flat.payload["trend_direction"]=="FLAT",flat.payload)
print("flat trend classification: PASS")

bad=mod.evaluate_advanced_capability("forecast_trend",{
    "values":[1,2,3],
    "horizon":100,
    "max_horizon":12,
})
a(bad.boundary==mod.AdvancedBoundary.INVALID_INPUT,bad)
print("forecast horizon bound: PASS")

print("SHY v0.46 FORECAST & TREND INTELLIGENCE: PASS")

import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v040",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v040"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

ready=mod.evaluate_advanced_capability("financial_planning",{
    "scenarios":[
        {"name":"base","revenue":10000,"costs":6000,"investment":2000,"probability":0.7},
        {"name":"downside","revenue":8000,"costs":6000,"investment":2000,"probability":0.3},
    ]
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
base=ready.payload["scenarios"][0]
a(base["operating_profit"]==4000.0,base)
a(base["net_after_investment"]==2000.0,base)
a(base["roi"]==1.0,base)
a(base["break_even_revenue"]==8000.0,base)
a(ready.payload["transaction_executed"] is False,ready.payload)
a(ready.payload["personalized_buy_sell_instruction"] is False,ready.payload)
print("financial scenario math: PASS")

invalid=mod.evaluate_advanced_capability("financial_planning",{
    "scenarios":[{"name":"bad","revenue":100,"costs":-1,"investment":0,"probability":1}]
})
a(invalid.boundary==mod.AdvancedBoundary.INVALID_INPUT,invalid)
print("financial input validation: PASS")

many=[{"name":f"s{i}","revenue":10,"costs":5,"investment":1,"probability":1} for i in range(5)]
bounded=mod.evaluate_advanced_capability("financial_planning",{"scenarios":many,"max_scenarios":2})
a(bounded.payload["scenario_count"]==2,bounded.payload)
a(bounded.payload["scenario_limit_enforced"] is False,bounded.payload)
print("financial scenario bound: PASS")

print("SHY v0.40 FINANCIAL PLANNING INTELLIGENCE: PASS")

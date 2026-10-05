import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v036",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v036"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

ready=mod.evaluate_advanced_capability("data_workspace",{
    "columns":["id","revenue","status"],
    "rows":[
        {"id":1,"revenue":100,"status":"ok"},
        {"id":2,"revenue":None,"status":"ok"},
        {"id":3,"revenue":300,"status":""},
    ],
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.payload["row_count_profiled"]==3,ready.payload)
a(ready.payload["missing_rates"]["revenue"]==0.333333,ready.payload)
a(ready.payload["missing_rates"]["status"]==0.333333,ready.payload)
a(ready.payload["raw_rows_returned"] is False,ready.payload)
a(ready.payload["dataset_mutated"] is False,ready.payload)
a(ready.payload["query_executed"] is False,ready.payload)
print("data workspace profiling: PASS")

duplicate=mod.evaluate_advanced_capability("data_workspace",{
    "columns":["id","id"],
    "rows":[],
})
a(duplicate.boundary==mod.AdvancedBoundary.INVALID_INPUT,duplicate)
print("duplicate column rejection: PASS")

rows=[{"id":i} for i in range(8)]
bounded=mod.evaluate_advanced_capability("data_workspace",{
    "columns":["id"],
    "rows":rows,
    "max_rows":3,
})
a(bounded.payload["row_count_profiled"]==3,bounded.payload)
a(bounded.payload["sample_limit_enforced"] is False,bounded.payload)
print("data row bound: PASS")

print("SHY v0.36 DATA WORKSPACE INTELLIGENCE: PASS")

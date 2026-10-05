import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v038",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v038"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

ready=mod.evaluate_advanced_capability("research_orchestration",{
    "current_required":True,
    "sources":[
        {"source_id":"secondary","authority":"SECONDARY","age_days":2,"claim":"same fact","provenance_available":True},
        {"source_id":"primary","authority":"PRIMARY","age_days":1,"claim":"same fact","provenance_available":True},
    ],
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.payload["selected_source_ids"]==["primary","secondary"],ready.payload)
a(ready.payload["authoritative_source_count"]==1,ready.payload)
a(ready.payload["external_fetch_performed"] is False,ready.payload)
a(ready.payload["source_content_returned"] is False,ready.payload)
print("research source ranking: PASS")

stale=mod.evaluate_advanced_capability("research_orchestration",{
    "current_required":True,
    "max_age_days":7,
    "sources":[{"source_id":"old","authority":"PRIMARY","age_days":30,"claim":"fact","provenance_available":True}],
})
a(stale.boundary==mod.AdvancedBoundary.DATA_REQUIRED,stale)
a(stale.reason=="fresh_current_sources_required",stale.reason)
print("current research freshness boundary: PASS")

conflict=mod.evaluate_advanced_capability("research_orchestration",{
    "sources":[
        {"source_id":"a","authority":"PRIMARY","age_days":1,"claim":"value is 10","provenance_available":True},
        {"source_id":"b","authority":"AUTHORITATIVE","age_days":1,"claim":"value is 20","provenance_available":True},
    ],
})
a(conflict.boundary==mod.AdvancedBoundary.CONFLICT,conflict)
print("research conflict detection: PASS")

missing=mod.evaluate_advanced_capability("research_orchestration",{
    "sources":[{"source_id":"x","authority":"PRIMARY","age_days":1,"claim":"x","provenance_available":False}],
})
a(missing.boundary==mod.AdvancedBoundary.DATA_REQUIRED,missing)
print("research provenance requirement: PASS")

print("SHY v0.38 RESEARCH ORCHESTRATION: PASS")

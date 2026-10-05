import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v035",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v035"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

ready=mod.evaluate_advanced_capability("document_intelligence",{
    "source_id":"doc-1",
    "sections":[
        {"section_id":"s1","page":1,"text":"Quarterly revenue increased.","provenance_available":True},
        {"section_id":"s2","page":2,"text":"Operating margin improved.","provenance_available":True},
    ],
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.payload["citation_ids"]==["doc-1:s1","doc-1:s2"],ready.payload)
a(ready.payload["raw_text_returned"] is False,ready.payload)
a(ready.side_effect_performed is False,ready)
print("document provenance analysis: PASS")

missing=mod.evaluate_advanced_capability("document_intelligence",{
    "source_id":"doc-2",
    "sections":[{"section_id":"s1","page":1,"text":"x","provenance_available":False}],
})
a(missing.boundary==mod.AdvancedBoundary.DATA_REQUIRED,missing)
a(missing.reason=="section_provenance_required",missing.reason)
print("document provenance requirement: PASS")

sensitive=mod.evaluate_advanced_capability("document_intelligence",{
    "source_id":"doc-3",
    "sections":[{"section_id":"s1","page":1,"text":"API key secret value","provenance_available":True}],
})
a(sensitive.payload["sensitive_content_detected"] is True,sensitive.payload)
a(sensitive.payload["redaction_required"] is True,sensitive.payload)
a(sensitive.payload["raw_text_returned"] is False,sensitive.payload)
print("sensitive document redaction boundary: PASS")

many=[{"section_id":f"s{i}","page":i+1,"text":"safe","provenance_available":True} for i in range(5)]
bounded=mod.evaluate_advanced_capability("document_intelligence",{"source_id":"doc-4","sections":many,"max_sections":2})
a(bounded.payload["section_count"]==2,bounded.payload)
a(bounded.payload["section_limit_enforced"] is False,bounded.payload)
print("document section bound: PASS")

print("SHY v0.35 DOCUMENT INTELLIGENCE: PASS")

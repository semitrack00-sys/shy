import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v045",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v045"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c:
        raise AssertionError(m)

assoc=mod.evaluate_advanced_capability("experiment_causal",{
    "control":{"mean":100,"sample_size":1000},
    "treatment":{"mean":110,"sample_size":1000},
    "randomized":False,
    "verified_design":False,
})
a(assoc.boundary==mod.AdvancedBoundary.READY,assoc)
a(assoc.payload["absolute_effect"]==10.0,assoc.payload)
a(assoc.payload["causal_claim_supported"] is False,assoc.payload)
a(assoc.payload["experiment_launched"] is False,assoc.payload)
print("association-only experiment analysis: PASS")

causal=mod.evaluate_advanced_capability("experiment_causal",{
    "control":{"mean":100,"sample_size":1000},
    "treatment":{"mean":110,"sample_size":1000},
    "randomized":True,
    "verified_design":True,
    "known_confounders":[],
})
a(causal.payload["causal_claim_supported"] is True,causal.payload)
a(causal.payload["causal_interpretation"]=="CAUSAL_EVIDENCE_SUPPORTED",causal.payload)
print("verified randomized causal boundary: PASS")

confounded=mod.evaluate_advanced_capability("experiment_causal",{
    "control":{"mean":100,"sample_size":100},
    "treatment":{"mean":120,"sample_size":100},
    "randomized":True,
    "verified_design":True,
    "known_confounders":["seasonality"],
})
a(confounded.payload["causal_claim_supported"] is False,confounded.payload)
print("known confounder blocks causal claim: PASS")

print("SHY v0.45 EXPERIMENT & CAUSAL INTELLIGENCE: PASS")

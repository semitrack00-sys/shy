import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"services"/"agent-runtime"/"preference_intelligence.py"
s=importlib.util.spec_from_file_location("p",P); p=importlib.util.module_from_spec(s); sys.modules["p"]=p; s.loader.exec_module(p)
def a(c,m):
    if not c: raise AssertionError(m)

explicit=p.evaluate_preference_update(p.PreferenceUpdate("response_style","concise",p.PreferenceSource.EXPLICIT,p.PreferenceScope.USER,1.0))
a(explicit.accepted and explicit.record is not None,"explicit")
print("explicit preference: PASS")

verified=p.evaluate_preference_update(p.PreferenceUpdate("report_format","table",p.PreferenceSource.VERIFIED_OUTCOME,p.PreferenceScope.WORKSPACE,0.9))
a(verified.accepted,"verified")
print("verified preference: PASS")

implicit=p.evaluate_preference_update(p.PreferenceUpdate("theme","dark",p.PreferenceSource.INFERRED,p.PreferenceScope.USER,0.9))
a(not implicit.accepted and implicit.reason=="implicit_preference_learning_disabled","implicit rejection")
print("implicit preference rejection: PASS")

protected=p.evaluate_preference_update(p.PreferenceUpdate("medical_condition","x",p.PreferenceSource.EXPLICIT,p.PreferenceScope.USER,1.0))
a(not protected.accepted and protected.reason=="protected_preference_category","protected")
print("protected preference rejection: PASS")

low=p.evaluate_preference_update(p.PreferenceUpdate("report_format","table",p.PreferenceSource.VERIFIED_OUTCOME,p.PreferenceScope.USER,0.5))
a(not low.accepted and low.reason=="verified_preference_confidence_too_low","confidence")
print("verified preference confidence bound: PASS")

records=(
 explicit.record,
 verified.record,
 p.PreferenceRecord("language","English",p.PreferenceSource.EXPLICIT,p.PreferenceScope.USER,0.95),
 p.PreferenceRecord("response_style","detailed",p.PreferenceSource.EXPLICIT,p.PreferenceScope.USER,0.8),
)
profile=p.build_preference_profile(tuple(x for x in records if x is not None),scope=p.PreferenceScope.USER)
a(all(x.scope==p.PreferenceScope.USER for x in profile),"scope")
a(sum(1 for x in profile if x.key=="response_style")==1,"dedup")
a(next(x for x in profile if x.key=="response_style").value=="detailed","latest value")
print("scoped preference profile: PASS")

print("SHY v0.26 PREFERENCE CONTEXT CHECKPOINT: PASS")

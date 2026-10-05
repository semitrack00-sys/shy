import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "services" / "agent-runtime" / "preference_learning.py"
spec = importlib.util.spec_from_file_location("shy_pref_v026", P)
pref = importlib.util.module_from_spec(spec)
sys.modules["shy_pref_v026"] = pref
spec.loader.exec_module(pref)

def a(c, m):
    if not c:
        raise AssertionError(m)

ok = pref.evaluate_preference(pref.PreferenceUpdate(
    scope=pref.PreferenceScope.USER,
    key="response_length",
    value="concise",
    explicit=True,
))
a(ok.decision == pref.PreferenceDecision.ACCEPTED, ok)
state = pref.apply_preference({}, ok)
a(state["response length"] == "concise", state)
print("explicit preference learning: PASS")

implicit = pref.evaluate_preference(pref.PreferenceUpdate(
    scope=pref.PreferenceScope.USER,
    key="response_length",
    value="long",
    explicit=False,
))
a(implicit.decision == pref.PreferenceDecision.REJECTED, implicit)
a(implicit.reason == "explicit_preference_required", implicit.reason)
print("implicit profiling rejected: PASS")

for key in ("security policy", "permission level", "approval rules", "tool_policy"):
    r = pref.evaluate_preference(pref.PreferenceUpdate(
        scope=pref.PreferenceScope.WORKSPACE,
        key=key,
        value="relaxed",
        explicit=True,
    ))
    a(r.decision == pref.PreferenceDecision.REJECTED, key)
    a(r.reason == "protected_policy_target", r.reason)
print("protected policy preferences rejected: PASS")

for key in ("religion", "political ideology", "medical condition"):
    r = pref.evaluate_preference(pref.PreferenceUpdate(
        scope=pref.PreferenceScope.USER,
        key=key,
        value="example",
        explicit=True,
    ))
    a(r.decision == pref.PreferenceDecision.REJECTED, key)
    a(r.reason == "sensitive_profile_target", r.reason)
print("sensitive profiling rejected: PASS")

base = {f"k{i}": "v" for i in range(3)}
extra = pref.evaluate_preference(pref.PreferenceUpdate(
    scope=pref.PreferenceScope.USER,
    key="new_key",
    value="new",
    explicit=True,
))
bounded = pref.apply_preference(base, extra, max_preferences=3)
a("new key" not in bounded, bounded)
print("preference count bound: PASS")

public = pref.public_preference_metadata(ok)
a("value" not in public, "public metadata must not echo preference value")
a(public["value_stored"] is True, public)
print("preference metadata privacy: PASS")

print("SHY v0.26 BOUNDED PREFERENCE LEARNING: PASS")

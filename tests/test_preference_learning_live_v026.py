import os
import httpx

BASE=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8026").rstrip("/")
T=60.0

def a(c,m):
    if not c: raise AssertionError(m)

h=httpx.get(BASE+"/health",timeout=T); a(h.status_code==200,h.text)
p=h.json(); a(p.get("version")=="0.26.0",p); a(p.get("application_healthy") is True,"health")
caps=p.get("preference_capabilities") or {}
a(caps.get("explicit_preferences") is True,caps)
a(caps.get("implicit_profiling") is False,caps)
a(caps.get("persistent_preference_storage") is False,caps)
print("v0.26 live health: PASS")

def post(payload):
    r=httpx.post(BASE+"/preferences/evaluate",json=payload,timeout=T)
    a(r.status_code==200,r.text)
    return r.json()

ok=post({"scope":"USER","key":"response_length","value":"concise","explicit":True})
a(ok["preference"]["decision"]=="ACCEPTED",ok)
a(ok["persistent_change_applied"] is False,ok)
print("live explicit preference: PASS")

implicit=post({"scope":"USER","key":"response_length","value":"long","explicit":False})
a(implicit["preference"]["decision"]=="REJECTED",implicit)
a(implicit["preference"]["reason"]=="explicit_preference_required",implicit)
print("live implicit profiling rejection: PASS")

sensitive=post({"scope":"USER","key":"medical condition","value":"example","explicit":True})
a(sensitive["preference"]["decision"]=="REJECTED",sensitive)
a(sensitive["preference"]["reason"]=="sensitive_profile_target",sensitive)
print("live sensitive-profile rejection: PASS")

policy=post({"scope":"WORKSPACE","key":"security policy","value":"relaxed","explicit":True})
a(policy["preference"]["decision"]=="REJECTED",policy)
a(policy["preference"]["reason"]=="protected_policy_target",policy)
print("live policy-learning rejection: PASS")

print("SHY v0.26 PREFERENCE LEARNING LIVE GATE: PASS")

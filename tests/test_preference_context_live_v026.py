import os,httpx
B=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8026").rstrip("/");T=60
def a(c,m):
    if not c: raise AssertionError(m)
h=httpx.get(B+"/health",timeout=T);p=h.json();a(p["version"]=="0.26.0",p);pc=p["preference_capabilities"];a(pc["implicit_behavior_learning"] is False,"implicit");a(pc["persistent_preference_profile"] is False,"persist");print("v0.26 health: PASS")

r=httpx.post(B+"/preference/evaluate",json={"key":"response_style","value":"concise","source":"EXPLICIT","scope":"USER"},timeout=T);q=r.json()["preference"];a(q["accepted"] is True,q);a(r.json()["persistent_change_applied"] is False,"persist");print("live explicit preference: PASS")

r=httpx.post(B+"/preference/evaluate",json={"key":"theme","value":"dark","source":"INFERRED","scope":"USER"},timeout=T);q=r.json()["preference"];a(q["accepted"] is False and q["reason"]=="implicit_preference_learning_disabled",q);print("live implicit rejection: PASS")

r=httpx.post(B+"/preference/evaluate",json={"key":"medical_condition","value":"x","source":"EXPLICIT","scope":"USER"},timeout=T);q=r.json()["preference"];a(q["accepted"] is False and q["reason"]=="protected_preference_category",q);print("live protected category: PASS")

records=[
 {"key":"response_style","value":"concise","source":"EXPLICIT","scope":"USER","confidence":1.0},
 {"key":"report_format","value":"table","source":"VERIFIED_OUTCOME","scope":"WORKSPACE","confidence":0.9},
 {"key":"language","value":"English","source":"EXPLICIT","scope":"USER","confidence":0.95}
]
r=httpx.post(B+"/preference/profile-preview",json={"records":records,"scope":"USER"},timeout=T);prof=r.json()["profile"];a(prof["count"]==2,prof);a(all(x["scope"]=="USER" for x in prof["preferences"]),prof);print("live scoped profile preview: PASS")

print("SHY v0.26 PREFERENCE CONTEXT LIVE GATE: PASS")

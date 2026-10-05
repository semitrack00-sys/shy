import os,httpx
B=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8028").rstrip("/");T=60
def a(c,m):
    if not c: raise AssertionError(m)

h=httpx.get(B+"/health",timeout=T);a(h.status_code==200,h.text);p=h.json()
a(p["version"]=="0.28.0",p);a(p["application_healthy"] is True,"health")
rc=p["reliability_capabilities"];a(rc["self_certification"] is False,rc);a(rc["max_revisions"]==3,rc);a(rc["automatic_self_modification"] is False,rc)
print("v0.28 health: PASS")

def evaluate(payload):
    r=httpx.post(B+"/reliability/evaluate",json=payload,timeout=T);a(r.status_code==200,r.text);return r.json()

q=evaluate({"correctness":.95,"grounding":.93,"consistency":.92,"completeness":.9,"safety":.98,"evidence_available":True})
a(q["reliability"]["boundary"]=="PASS",q)
print("live reliability pass: PASS")

q=evaluate({"correctness":.8,"grounding":.82,"consistency":.75,"completeness":.6,"safety":.95,"evidence_available":True})
a(q["reliability"]["boundary"]=="REVISE",q);a(q["reliability"]["revision_recommended"] is True,q);a(q["automatic_revision_performed"] is False,"automatic revision")
print("live reliability revise: PASS")

q=evaluate({"correctness":.95,"grounding":.95,"consistency":.95,"completeness":.95,"safety":.3,"evidence_available":True})
a(q["reliability"]["boundary"]=="BLOCK",q);a(float(q["reliability"]["confidence_cap"])<=.35,q)
print("live safety block: PASS")

q=evaluate({"correctness":.8,"grounding":.6,"consistency":.9,"completeness":.9,"safety":.95,"evidence_available":False})
a(q["reliability"]["boundary"]=="INSUFFICIENT_EVIDENCE",q);a(float(q["reliability"]["confidence_cap"])<=.55,q)
print("live insufficient evidence: PASS")

samples=[
 {"predicted_confidence":.9,"success":True,"verified":True},
 {"predicted_confidence":.8,"success":False,"verified":True},
 {"predicted_confidence":1.0,"success":False,"verified":False},
]
for path in ("/reliability/calibration","/reliability/calibrate"):
    r=httpx.post(B+path,json={"samples":samples},timeout=T);a(r.status_code==200,r.text);body=r.json();cal=body["calibration"]
    a(cal["sample_count"]==2,cal);a(0<=cal["brier_score"]<=1,cal);a(body["persistent_change_applied"] is False,"persistent mutation");a(body["automatic_self_modification"] is False,"self mutation")
print("live verified calibration aliases: PASS")

print("SHY v0.28 RELIABILITY LIVE GATE: PASS")

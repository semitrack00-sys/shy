import os,httpx
B=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8028").rstrip("/");T=60
def a(c,m):
    if not c: raise AssertionError(m)
h=httpx.get(B+"/health",timeout=T);p=h.json();a(p["version"]=="0.28.0",p);rc=p["reliability_capabilities"];a(rc["automatic_self_modification"] is False,rc);a(rc["bounded_revision_recommendation"] is True,rc);print("v0.28 health: PASS")
r=httpx.post(B+"/reliability/evaluate",json={"correctness":0.95,"grounding":0.93,"consistency":0.92,"completeness":0.9,"safety":0.98,"evidence_available":True},timeout=T);q=r.json()["reliability"];a(q["boundary"]=="PASS",q);print("live reliability pass: PASS")
r=httpx.post(B+"/reliability/evaluate",json={"correctness":0.95,"grounding":0.95,"consistency":0.95,"completeness":0.95,"safety":0.3,"evidence_available":True},timeout=T);q=r.json()["reliability"];a(q["boundary"]=="BLOCK",q);print("live safety block: PASS")
samples=[{"predicted_confidence":0.9,"success":True,"verified":True},{"predicted_confidence":0.8,"success":False,"verified":True},{"predicted_confidence":1.0,"success":False,"verified":False}]
r=httpx.post(B+"/reliability/calibration",json={"samples":samples},timeout=T);q=r.json()["calibration"];a(q["sample_count"]==2,q);a(r.json()["automatic_self_modification"] is False,"no auto mutation");print("live verified calibration: PASS")
print("SHY v0.28 RELIABILITY LIVE GATE: PASS")

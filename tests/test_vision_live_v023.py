import os
import httpx

BASE_URL=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8023").rstrip("/")
TIMEOUT=60.0

def a(c,m):
    if not c: raise AssertionError(m)

h=httpx.get(f"{BASE_URL}/health",timeout=TIMEOUT); a(h.status_code==200,h.text)
p=h.json(); a(p.get("version")=="0.23.0",p); a(p.get("application_healthy") is True,"health")
caps=p.get("vision_capabilities") or {}
a(caps.get("vision_planning") is True,"planning"); a(caps.get("raw_image_inference") is False,"raw image must remain off")
a(caps.get("real_person_identity_recognition") is False,"identity must remain off")
print("v0.23 live health: PASS")

r=httpx.post(f"{BASE_URL}/vision/plan",json={"prompt":"Read the text in this screenshot","has_image":True,"provider_available":False},timeout=TIMEOUT)
a(r.status_code==200,r.text); plan=r.json().get("vision_plan") or {}
a(plan.get("boundary")=="PROVIDER_REQUIRED",plan); a(r.json().get("raw_image_inference_performed") is False,"no fake inference")
print("live provider-required boundary: PASS")

r=httpx.post(f"{BASE_URL}/vision/plan",json={"prompt":"Who is this person?","has_image":True,"provider_available":True},timeout=TIMEOUT)
plan=r.json().get("vision_plan") or {}; a(plan.get("boundary")=="DENIED",plan); a(plan.get("identity_recognition_allowed") is False,"identity")
print("live identity denial: PASS")

r=httpx.post(f"{BASE_URL}/vision/observation",json={
 "source_id":"img-live-1","provider":"approved-vision","mime_type":"image/png","width":1280,"height":720,
 "summary":"A settings screen","extracted_text":"Settings Security","labels":["screen","settings"],
 "regions":[{"label":"Security tab","confidence":0.93,"bbox":[0.1,0.1,0.4,0.3]}],
 "contains_people":False,"provenance_available":True},timeout=TIMEOUT)
a(r.status_code==200,r.text); body=r.json(); a(body.get("status")=="ok",body)
obs=body.get("observation") or {}; a(obs.get("provider")=="approved-vision",obs); a(obs.get("identity_inference_performed") is False,"identity inference")
print("live structured observation: PASS")

r=httpx.post(f"{BASE_URL}/vision/observation",json={
 "source_id":"img-live-2","provider":"approved-vision","mime_type":"image/jpeg","width":100,"height":100,
 "provenance_available":False},timeout=TIMEOUT)
a(r.status_code==200,r.text); body=r.json(); a(body.get("status")=="rejected",body); a(body.get("rejected_reason")=="visual_provenance_required",body)
print("live provenance rejection: PASS")

print("SHY v0.23 VISION LIVE GATE: PASS")

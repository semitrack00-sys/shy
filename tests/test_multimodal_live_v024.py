import os, httpx
BASE=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8024").rstrip("/")
T=60.0
def a(c,m):
    if not c: raise AssertionError(m)

h=httpx.get(f"{BASE}/health",timeout=T); a(h.status_code==200,h.text)
p=h.json(); a(p.get("version")=="0.24.0",p); a(p.get("application_healthy") is True,"health")
mc=p.get("multimodal_capabilities") or {}; a(mc.get("cross_modality_conflict_detection") is True,mc)
a(mc.get("raw_audio") is False and mc.get("raw_image_inference") is False,"raw modality truthfulness")
print("v0.24 live health: PASS")

evidence=[
 {"modality":"TEXT","source_id":"t1","content":"Truck 12 delayed","claims":{"status":"delayed"}},
 {"modality":"VOICE","source_id":"v1","content":"Truck 12 delayed","claims":{"status":"delayed"}},
 {"modality":"VISION","source_id":"i1","content":"dashboard delayed","provenance_available":True,"claims":{"status":"delayed"}}
]
r=httpx.post(f"{BASE}/multimodal/fuse",json={"evidence":evidence,"max_sources":12},timeout=T)
a(r.status_code==200,r.text); b=r.json(); f=b.get("fusion") or {}
a(f.get("boundary")=="FUSED",f); a(f.get("source_count")==3,f); a(set(f.get("modalities") or [])=={"TEXT","VOICE","VISION"},f)
a(b.get("hidden_reasoning_exposed") is False,"hidden reasoning")
print("live consistent fusion: PASS")

conflict=[
 {"modality":"TEXT","source_id":"t2","content":"active","claims":{"status":"active"}},
 {"modality":"VISION","source_id":"i2","content":"stopped","provenance_available":True,"claims":{"status":"stopped"}}
]
r=httpx.post(f"{BASE}/multimodal/fuse",json={"evidence":conflict},timeout=T)
f=r.json().get("fusion") or {}; a(f.get("boundary")=="CONFLICT_REQUIRES_CLARIFICATION",f); a(len(f.get("conflicts") or [])==1,f)
print("live multimodal conflict: PASS")

bad=[{"modality":"VISION","source_id":"i3","content":"x","provenance_available":False}]
r=httpx.post(f"{BASE}/multimodal/fuse",json={"evidence":bad},timeout=T)
b=r.json(); a(b.get("status")=="rejected",b); a(b.get("rejected_reason")=="vision_provenance_required",b)
print("live provenance rejection: PASS")

print("SHY v0.24 MULTIMODAL LIVE GATE: PASS")

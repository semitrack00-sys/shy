import os,httpx
B=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8027").rstrip("/");T=60
def a(c,m):
    if not c: raise AssertionError(m)
h=httpx.get(B+"/health",timeout=T);p=h.json();a(p["version"]=="0.27.0",p);gc=p["knowledge_graph_capabilities"];a(gc["cross_scope_edges"] is False,"scope");a(gc["persistent_graph"] is False,"persist");print("v0.27 health: PASS")
nodes=[{"entity_id":"e1","name":"Project Atlas","entity_type":"PROJECT","scope_id":"ws1","aliases":["Atlas"]},{"entity_id":"e2","name":"PostgreSQL","entity_type":"DATABASE","scope_id":"ws1","aliases":["Postgres"]},{"entity_id":"e3","name":"Strict Consistency","entity_type":"REQUIREMENT","scope_id":"ws1"}]
edges=[{"source_id":"e1","target_id":"e2","relation":"USES","confidence":0.95,"provenance_ids":["k1"]},{"source_id":"e1","target_id":"e3","relation":"REQUIRES","confidence":0.98,"provenance_ids":["k2"]}]
r=httpx.post(B+"/graph/build",json={"nodes":nodes,"edges":edges},timeout=T);b=r.json();a(b["status"]=="ok",b);a(b["graph"]["node_count"]==3,b);a(b["persistent_change_applied"] is False,"persist");print("live graph build: PASS")
r=httpx.post(B+"/graph/neighbors",json={"nodes":nodes,"edges":edges,"entity_id":"e1","depth":1},timeout=T);b=r.json();a(b["status"]=="ok",b);a(b["graph"]["edge_count"]==2,b);print("live neighbor traversal: PASS")
cross=[nodes[0],{"entity_id":"x","name":"Other","entity_type":"PROJECT","scope_id":"ws2"}]
r=httpx.post(B+"/graph/build",json={"nodes":cross,"edges":[]},timeout=T);b=r.json();a(b["status"]=="rejected" and b["reason"]=="cross_scope_nodes_denied",b);print("live cross-scope denial: PASS")
bad=[{"source_id":"e1","target_id":"e2","relation":"USES","confidence":0.8,"provenance_ids":[]}]
r=httpx.post(B+"/graph/build",json={"nodes":nodes,"edges":bad},timeout=T);b=r.json();a(b["status"]=="rejected" and b["reason"]=="relationship_provenance_required",b);print("live graph provenance rejection: PASS")
print("SHY v0.27 KNOWLEDGE GRAPH LIVE GATE: PASS")

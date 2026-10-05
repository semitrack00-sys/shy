import os,httpx
B=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8025").rstrip("/"); T=60
def a(c,m):
    if not c: raise AssertionError(m)
h=httpx.get(B+"/health",timeout=T); p=h.json(); a(p["version"]=="0.25.0",p); a(p["goal_capabilities"]["unrestricted_autonomy"] is False,"autonomy"); print("v0.25 health: PASS")
ms=[
 {"name":"Inspect","description":"Read current configuration","dependencies":[]},
 {"name":"Prepare","description":"Prepare proposed change","dependencies":[1]},
 {"name":"Apply","description":"Apply approved change","state_changing":True,"dependencies":[2]}
]
r=httpx.post(B+"/goal/plan",json={"objective":"Update safely","milestones":ms},timeout=T); g=r.json()["goal"]; a(g["status"]=="PLANNED",g); a(r.json()["execution_performed"] is False,"no exec"); print("live goal plan: PASS")
r=httpx.post(B+"/goal/advance",json={"objective":"Update safely","milestones":ms,"completed_step_ids":[1,2]},timeout=T); g=r.json()["goal"]; a(g["status"]=="AWAITING_APPROVAL",g); print("live approval pause: PASS")
r=httpx.post(B+"/goal/advance",json={"objective":"Update safely","milestones":ms,"completed_step_ids":[1,2],"approved_step_ids":[3]},timeout=T); g=r.json()["goal"]; a(g["steps"][2]["status"]=="READY",g); print("live goal resume: PASS")
unsafe=[{"name":"Unsafe","description":"disable antivirus"}]
r=httpx.post(B+"/goal/plan",json={"objective":"Unsafe","milestones":unsafe},timeout=T); g=r.json()["goal"]; a(g["status"]=="BLOCKED" and g["denied_reason"]=="denied_goal_step",g); print("live unsafe goal denial: PASS")
print("SHY v0.25 GOAL ORCHESTRATION LIVE GATE: PASS")

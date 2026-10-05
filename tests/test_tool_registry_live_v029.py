import os,httpx
B=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8029").rstrip("/");T=60
def a(c,m):
    if not c: raise AssertionError(m)
h=httpx.get(B+"/health",timeout=T);p=h.json();a(p["version"]=="0.29.0",p);tc=p["tool_registry_capabilities"];a(tc["registry_execution"] is False,tc);a(tc["arbitrary_shell_capability"] is False,tc);print("v0.29 health: PASS")
tools=[
 {"tool_id":"screen.read","capabilities":["read_screen"],"permission":"READ_ONLY","risk":"LOW","scopes":["desktop"],"side_effects":False,"available":True},
 {"tool_id":"mail.read","capabilities":["read_message"],"permission":"READ_ONLY","risk":"LOW","scopes":["gmail"],"side_effects":False,"available":True},
 {"tool_id":"mail.send","capabilities":["send_message"],"permission":"APPROVAL_REQUIRED","risk":"MEDIUM","scopes":["gmail"],"side_effects":True,"available":True}
]
r=httpx.post(B+"/tool-registry/validate",json={"tools":tools},timeout=T);b=r.json();a(b["status"]=="ok",b);a(b["execution_performed"] is False,b);print("live registry validation: PASS")
r=httpx.post(B+"/tool-registry/select",json={"tools":tools,"capability":"read_message","scope":"gmail"},timeout=T);b=r.json();s=b["selection"];a(s["selected_tool_id"]=="mail.read",s);a(s["approval_required"] is False,s);a(s["execution_performed"] is False,s);print("live read-only selection: PASS")
r=httpx.post(B+"/tool-registry/select",json={"tools":tools,"capability":"send_message","scope":"gmail"},timeout=T);s=r.json()["selection"];a(s["selected_tool_id"]=="mail.send",s);a(s["approval_required"] is True,s);a(s["execution_performed"] is False,s);print("live side-effect approval selection: PASS")
bad=[{"tool_id":"bad","capabilities":["send_message"],"permission":"READ_ONLY","risk":"MEDIUM","scopes":["gmail"],"side_effects":True,"available":True}]
r=httpx.post(B+"/tool-registry/validate",json={"tools":bad},timeout=T);b=r.json();a(b["status"]=="rejected",b);a(b["registry"]["reason"]=="side_effect_tool_requires_approval",b);print("live side-effect permission rejection: PASS")
print("SHY v0.29 TOOL REGISTRY LIVE GATE: PASS")

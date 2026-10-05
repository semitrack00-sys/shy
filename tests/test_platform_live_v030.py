import os,httpx
B=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8030").rstrip("/");T=60
def a(c,m):
    if not c: raise AssertionError(m)
h=httpx.get(B+"/health",timeout=T);a(h.status_code==200,h.text);p=h.json();a(p["version"]=="0.30.0",p);a(p["application_healthy"] is True,p)
pc=p["platform_checkpoint"];a(pc["sequence_v020_to_v030_complete"] is True,pc);a(pc["required_disabled_invariants_enforced"] is True,pc)
print("v0.30 integrated health: PASS")
r=httpx.get(B+"/platform/capabilities",timeout=T);a(r.status_code==200,r.text);b=r.json();m=b["platform"];a(m["version"]=="0.30.0",m);a(m["sequence_complete"] is True,m);a(m["required_disabled_invariants_hold"] is True,m)
states={x["capability_id"]:x["state"] for x in m["capabilities"]}
for key in ("raw_audio_capture","raw_image_inference","unrestricted_computer_execution","arbitrary_shell_execution","real_person_identity_recognition","autonomous_security_policy_rewrite"):
    a(states[key]=="DISABLED",(key,states[key]))
a(b["hidden_reasoning_exposed"] is False,b)
print("live platform manifest invariants: PASS")
a(p["interaction_capabilities"]["computer_execution"] is False,p["interaction_capabilities"])
a(p["vision_capabilities"]["raw_image_inference"] is False,p["vision_capabilities"])
a(p["goal_capabilities"]["unrestricted_autonomy"] is False,p["goal_capabilities"])
a(p["preference_capabilities"]["implicit_behavior_learning"] is False,p["preference_capabilities"])
a(p["tool_registry_capabilities"]["registry_execution"] is False,p["tool_registry_capabilities"])
print("cross-capability negative invariants: PASS")
print("SHY v0.30 INTEGRATED PLATFORM LIVE GATE: PASS")

import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"services"/"agent-runtime"/"platform_manifest.py"
s=importlib.util.spec_from_file_location("p",P);p=importlib.util.module_from_spec(s);sys.modules["p"]=p;s.loader.exec_module(p)
def a(c,m):
    if not c: raise AssertionError(m)

m=p.build_platform_manifest(version="0.30.0")
a(m.version=="0.30.0",m)
a(m.sequence_complete is True,m)
a(m.required_disabled_invariants_hold is True,m)
print("v0.20-v0.30 sequence manifest: PASS")

states={x.capability_id:x.state for x in m.capabilities}
for key in ("raw_audio_capture","raw_image_inference","unrestricted_computer_execution","arbitrary_shell_execution","real_person_identity_recognition","autonomous_security_policy_rewrite"):
    a(states[key]==p.CapabilityState.DISABLED,key)
print("required disabled invariants: PASS")

a(states["expert_intelligence"]==p.CapabilityState.ACTIVE,states)
a(states["multimodal_fusion"]==p.CapabilityState.ACTIVE,states)
a(states["tool_capability_registry"]==p.CapabilityState.BOUNDED,states)
print("integrated capability states: PASS")

tampered=list(m.capabilities)
for i,item in enumerate(tampered):
    if item.capability_id=="arbitrary_shell_execution":
        tampered[i]=p.PlatformCapability(item.capability_id,item.introduced_version,p.CapabilityState.ACTIVE,item.safety_boundary)
bad=p.build_platform_manifest(version="0.30.0",capabilities=tuple(tampered))
a(bad.required_disabled_invariants_hold is False,bad)
print("platform invariant tamper detection: PASS")

pub=p.public_platform_manifest(m)
a(pub["sequence_complete"] is True,pub)
a(pub["required_disabled_invariants_hold"] is True,pub)
print("public platform manifest: PASS")

print("SHY v0.30 INTEGRATED PLATFORM CHECKPOINT: PASS")

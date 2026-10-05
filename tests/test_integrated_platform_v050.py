import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod
    spec.loader.exec_module(mod)
    return mod

advanced=load("shy_advanced_v050",ROOT/"services"/"agent-runtime"/"advanced_milestones.py")
manifest_mod=load("shy_manifest_v050",ROOT/"services"/"agent-runtime"/"platform_manifest.py")

def a(c,m):
    if not c:
        raise AssertionError(m)

manifest=manifest_mod.build_platform_manifest(version="0.50.0")
a(manifest.version=="0.50.0",manifest)
a(manifest.sequence_complete is True,manifest)
a(manifest.required_disabled_invariants_hold is True,manifest)

introduced={item.introduced_version for item in manifest.capabilities}
required_versions={f"0.{version}.0" for version in range(26,51)}
missing=sorted(required_versions-introduced)
a(not missing,f"missing requested versions: {missing}")
print("continuous v0.26-v0.50 manifest sequence: PASS")

required_disabled={
    "raw_audio_capture",
    "raw_image_inference",
    "unrestricted_computer_execution",
    "arbitrary_shell_execution",
    "real_person_identity_recognition",
    "autonomous_security_policy_rewrite",
}
states={item.capability_id:item.state.value for item in manifest.capabilities}
a(all(states.get(item)=="DISABLED" for item in required_disabled),states)
print("protected disabled invariants preserved: PASS")

subsystems=[
    {
        "capability_id":item.capability_id,
        "required": item.state.value!="DISABLED",
        "available": item.state.value!="DISABLED",
        "verified": True,
        "bounded": item.state.value in {"BOUNDED","ACTIVE"},
    }
    for item in manifest.capabilities
]
result=advanced.evaluate_advanced_capability("integrated_platform",{"subsystems":subsystems})
a(result.boundary==advanced.AdvancedBoundary.READY,result)
a(result.payload["integrated_ready"] is True,result.payload)
a(result.payload["production_deployed"] is False,result.payload)
a(result.payload["permission_expanded"] is False,result.payload)
a(result.payload["security_policy_rewritten"] is False,result.payload)
a(result.payload["autonomous_side_effects_enabled"] is False,result.payload)
print("integrated platform bounded readiness: PASS")

unsafe=advanced.evaluate_advanced_capability("integrated_platform",{
    "subsystems":[
        {"capability_id":"unsafe","required":True,"available":True,"verified":True,"bounded":False},
    ]
})
a(unsafe.boundary==advanced.AdvancedBoundary.CONFLICT,unsafe)
a(unsafe.payload["integrated_ready"] is False,unsafe.payload)
print("unbounded subsystem blocks integration: PASS")

print("SHY v0.50 INTEGRATED INTELLIGENCE PLATFORM: PASS")

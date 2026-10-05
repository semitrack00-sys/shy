import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"advanced_milestones.py"
spec=importlib.util.spec_from_file_location("shy_advanced_v037",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_advanced_v037"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

ready=mod.evaluate_advanced_capability("code_repository",{
    "files":[
        {"path":"src/db.py","dependencies":[]},
        {"path":"src/service.py","dependencies":["src/db.py"]},
        {"path":"src/api.py","dependencies":["src/service.py"]},
        {"path":"tests/test_api.py","dependencies":["src/api.py"]},
    ],
    "changed_paths":["src/db.py"],
})
a(ready.boundary==mod.AdvancedBoundary.READY,ready)
a(ready.payload["impacted_paths"]==["src/api.py","src/db.py","src/service.py","tests/test_api.py"],ready.payload)
a(ready.payload["code_execution_performed"] is False,ready.payload)
a(ready.payload["repository_write_performed"] is False,ready.payload)
print("repository impact analysis: PASS")

unsafe=mod.evaluate_advanced_capability("code_repository",{
    "files":[{"path":"../secret.txt","dependencies":[]}],
    "changed_paths":[],
})
a(unsafe.boundary==mod.AdvancedBoundary.PROTECTED_TARGET,unsafe)
print("repository traversal protection: PASS")

missing=mod.evaluate_advanced_capability("code_repository",{
    "files":[{"path":"src/a.py","dependencies":[]}],
    "changed_paths":["src/missing.py"],
})
a(missing.boundary==mod.AdvancedBoundary.DATA_REQUIRED,missing)
print("unknown changed path boundary: PASS")

print("SHY v0.37 CODE REPOSITORY INTELLIGENCE: PASS")

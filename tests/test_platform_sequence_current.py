import importlib.util
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST_PATH=ROOT/"services"/"agent-runtime"/"platform_manifest.py"
MAIN_PATH=ROOT/"services"/"core"/"main.py"

spec=importlib.util.spec_from_file_location("shy_platform_manifest_current",MANIFEST_PATH)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_platform_manifest_current"]=mod
spec.loader.exec_module(mod)

manifest=mod.build_platform_manifest()
main_text=MAIN_PATH.read_text(encoding="utf-8")
match=re.search(r'SHY_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"',main_text)
assert match, "SHY_VERSION missing from main.py"
runtime_version=match.group(1)

assert manifest.version==runtime_version, (manifest.version,runtime_version)
major,minor,patch=(int(part) for part in runtime_version.split("."))
assert major==0 and patch>=0, runtime_version
# Patch releases add bounded integration features without pretending the next
# numbered roadmap milestone was completed. Required milestone history stays
# on each minor version's initial .0 release.
expected=tuple(f"0.{value}.0" for value in range(20,minor+1))
assert tuple(mod._REQUIRED_SEQUENCE)==expected, (mod._REQUIRED_SEQUENCE,expected)
assert manifest.sequence_complete is True, "platform sequence must be complete"

introduced={item.introduced_version for item in manifest.capabilities}
for version in expected:
    assert version in introduced, f"no capability records version {version}"

assert manifest.required_disabled_invariants_hold is True
print(f"SHY PLATFORM SEQUENCE THROUGH {runtime_version}: PASS")


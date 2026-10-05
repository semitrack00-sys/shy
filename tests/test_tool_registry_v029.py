import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"services"/"agent-runtime"/"tool_capability_registry.py"
s=importlib.util.spec_from_file_location("t",P);t=importlib.util.module_from_spec(s);sys.modules["t"]=t;s.loader.exec_module(t)
def a(c,m):
    if not c: raise AssertionError(m)

tools=(
 t.ToolCapability("screen.read",("read_screen",),t.ToolPermission.READ_ONLY,t.ToolRisk.LOW,("desktop",),False,True),
 t.ToolCapability("mail.send",("send_message",),t.ToolPermission.APPROVAL_REQUIRED,t.ToolRisk.MEDIUM,("gmail",),True,True),
 t.ToolCapability("mail.read",("read_message",),t.ToolPermission.READ_ONLY,t.ToolRisk.LOW,("gmail",),False,True),
)
r=t.validate_registry(tools);a(r.accepted,r);print("tool registry validation: PASS")

sel=t.select_tool(r,capability="read_message",scope="gmail");a(sel.selected_tool_id=="mail.read",sel);a(sel.approval_required is False,sel);print("read-only tool selection: PASS")
sel=t.select_tool(r,capability="send_message",scope="gmail");a(sel.selected_tool_id=="mail.send",sel);a(sel.approval_required is True,sel);print("side-effect approval selection: PASS")

bad=t.validate_registry((t.ToolCapability("bad",("send_message",),t.ToolPermission.READ_ONLY,t.ToolRisk.MEDIUM,("gmail",),True,True),))
a(not bad.accepted and bad.reason=="side_effect_tool_requires_approval",bad);print("side-effect permission enforcement: PASS")

denied=t.validate_registry((t.ToolCapability("shell",("arbitrary_shell",),t.ToolPermission.APPROVAL_REQUIRED,t.ToolRisk.HIGH,("desktop",),True,True),))
a(not denied.accepted and denied.reason=="denied_tool_capability",denied);print("denied capability enforcement: PASS")

dup=t.validate_registry((tools[0],tools[0]));a(not dup.accepted and dup.reason=="duplicate_tool_id",dup);print("duplicate tool rejection: PASS")

pub=t.public_tool_selection(sel);a(pub["execution_performed"] is False,pub);print("selection is non-executing: PASS")
print("SHY v0.29 TOOL CAPABILITY REGISTRY: PASS")

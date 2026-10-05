import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"services"/"agent-runtime"/"goal_orchestration.py"
s=importlib.util.spec_from_file_location("g",P); g=importlib.util.module_from_spec(s); sys.modules["g"]=g; s.loader.exec_module(g)
def a(c,m):
    if not c: raise AssertionError(m)

milestones=(
 g.GoalMilestone("Inspect","Read current configuration"),
 g.GoalMilestone("Prepare","Prepare proposed change",dependencies=(1,)),
 g.GoalMilestone("Apply","Apply approved change",state_changing=True,dependencies=(2,)),
)
p=g.build_goal_plan("Update configuration safely",milestones)
a(p.status==g.GoalStatus.PLANNED,"planned"); a(p.steps[0].status==g.GoalStepStatus.READY,"first ready")
print("goal plan construction: PASS")

p1=g.advance_goal(p,completed_step_ids=(1,))
a(p1.status==g.GoalStatus.IN_PROGRESS,"in progress"); a(p1.steps[1].status==g.GoalStepStatus.READY,"second ready")
print("goal dependency advancement: PASS")

p2=g.advance_goal(p,completed_step_ids=(1,2))
a(p2.status==g.GoalStatus.AWAITING_APPROVAL,"approval"); a(p2.steps[2].status==g.GoalStepStatus.AWAITING_APPROVAL,"step approval")
print("goal approval pause: PASS")

p3=g.advance_goal(p,completed_step_ids=(1,2),approved_step_ids=(3,))
a(p3.steps[2].status==g.GoalStepStatus.READY,"approved ready")
p4=g.advance_goal(p,completed_step_ids=(1,2,3),approved_step_ids=(3,))
a(p4.status==g.GoalStatus.COMPLETED,"completed")
print("goal completion: PASS")

cancel=g.advance_goal(p,cancel=True); a(cancel.status==g.GoalStatus.CANCELLED,"cancel")
print("goal cancellation: PASS")

unsafe=g.build_goal_plan("Unsafe",(g.GoalMilestone("Bypass","disable antivirus"),))
a(unsafe.status==g.GoalStatus.BLOCKED and unsafe.denied_reason=="denied_goal_step","unsafe blocked")
print("unsafe goal denial: PASS")

invalid=g.build_goal_plan("Bad deps",(g.GoalMilestone("Step","x",dependencies=(2,)),))
a(invalid.denied_reason=="invalid_goal_dependency","dependency validation")
print("invalid dependency rejection: PASS")

many=tuple(g.GoalMilestone(str(i),"x") for i in range(20))
bounded=g.build_goal_plan("Bounded",many,max_steps=5)
a(len(bounded.steps)==5 and bounded.truncated is True,"step bound")
print("goal step bound: PASS")

print("SHY v0.25 GOAL ORCHESTRATION CHECKPOINT: PASS")

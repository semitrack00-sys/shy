import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"services"/"agent-runtime"/"long_horizon_planning.py"
s=importlib.util.spec_from_file_location("h",P);h=importlib.util.module_from_spec(s);sys.modules["h"]=h;s.loader.exec_module(h)
def a(c,m):
    if not c: raise AssertionError(m)
ph=(h.HorizonPhase(1,"Discover",(),True),h.HorizonPhase(2,"Build",(1,),True),h.HorizonPhase(3,"Validate",(2,),True))
p=h.build_horizon_plan(ph);a(p.status==h.HorizonStatus.NEEDS_REVIEW,p);a(p.max_replans==3,p);print("long-horizon plan: PASS")
bad=h.build_horizon_plan((h.HorizonPhase(1,"A",(2,)),h.HorizonPhase(2,"B",(1,))));a(bad.reason=="cyclic_phase_dependency",bad);print("cycle rejection: PASS")
many=tuple(h.HorizonPhase(i+1,str(i),(),False) for i in range(30));b=h.build_horizon_plan(many,max_phases=5);a(len(b.phases)==5 and b.truncated,b);print("phase bound: PASS")
r=h.replan_remaining(p,(1,),replan_count=0);a(len(r.phases)==2 and r.status==h.HorizonStatus.NEEDS_REVIEW,r);print("bounded replan: PASS")
stop=h.replan_remaining(p,(1,),replan_count=3);a(stop.status==h.HorizonStatus.BLOCKED and stop.reason=="replan_limit_reached",stop);print("replan limit: PASS")
a(h.public_horizon_plan(p)["execution_performed"] is False,"no execution");print("SHY v0.31 LONG-HORIZON PLANNING: PASS")

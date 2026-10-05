from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

class HorizonStatus(str, Enum):
    PLANNED="PLANNED"; NEEDS_REVIEW="NEEDS_REVIEW"; BLOCKED="BLOCKED"; COMPLETE="COMPLETE"

@dataclass(frozen=True)
class HorizonPhase:
    phase_id:int
    name:str
    dependencies:tuple[int,...]=()
    requires_review:bool=True

@dataclass(frozen=True)
class HorizonPlan:
    phases:tuple[HorizonPhase,...]
    status:HorizonStatus
    max_phases:int
    truncated:bool
    max_replans:int
    reason:str|None=None

def build_horizon_plan(phases:Sequence[HorizonPhase],*,max_phases:int=12,max_replans:int=3)->HorizonPlan:
    bound=max(1,min(int(max_phases),24)); replans=max(0,min(int(max_replans),3))
    selected=tuple(phases[:bound]); known={p.phase_id for p in selected}
    if not selected:
        return HorizonPlan((),HorizonStatus.BLOCKED,bound,False,replans,"phases_required")
    if len(known)!=len(selected):
        return HorizonPlan((),HorizonStatus.BLOCKED,bound,len(phases)>bound,replans,"duplicate_phase_id")
    for p in selected:
        if p.phase_id in p.dependencies or any(d not in known for d in p.dependencies):
            return HorizonPlan((),HorizonStatus.BLOCKED,bound,len(phases)>bound,replans,"invalid_phase_dependency")
    graph={p.phase_id:set(p.dependencies) for p in selected}
    visiting=set(); visited=set()
    def visit(n:int)->bool:
        if n in visiting:return False
        if n in visited:return True
        visiting.add(n)
        for d in graph[n]:
            if not visit(d):return False
        visiting.remove(n);visited.add(n);return True
    if not all(visit(n) for n in graph):
        return HorizonPlan((),HorizonStatus.BLOCKED,bound,len(phases)>bound,replans,"cyclic_phase_dependency")
    status=HorizonStatus.NEEDS_REVIEW if any(p.requires_review for p in selected) else HorizonStatus.PLANNED
    return HorizonPlan(selected,status,bound,len(phases)>bound,replans,None)

def replan_remaining(plan:HorizonPlan,completed:Sequence[int],*,replan_count:int)->HorizonPlan:
    if replan_count>=plan.max_replans:
        return HorizonPlan(plan.phases,HorizonStatus.BLOCKED,plan.max_phases,plan.truncated,plan.max_replans,"replan_limit_reached")
    done={int(x) for x in completed}
    remaining=tuple(p for p in plan.phases if p.phase_id not in done)
    if not remaining:
        return HorizonPlan((),HorizonStatus.COMPLETE,plan.max_phases,plan.truncated,plan.max_replans,None)
    return HorizonPlan(remaining,HorizonStatus.NEEDS_REVIEW,plan.max_phases,plan.truncated,plan.max_replans,None)

def public_horizon_plan(plan:HorizonPlan)->dict[str,object]:
    return {"status":plan.status.value,"phase_count":len(plan.phases),"max_phases":plan.max_phases,"truncated":plan.truncated,"max_replans":plan.max_replans,"reason":plan.reason,
            "phases":[{"phase_id":p.phase_id,"name":p.name,"dependencies":list(p.dependencies),"requires_review":p.requires_review} for p in plan.phases],
            "execution_performed":False}

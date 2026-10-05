import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"condition_intelligence.py"
spec=importlib.util.spec_from_file_location("shy_condition_v032",P)
mod=importlib.util.module_from_spec(spec)
sys.modules["shy_condition_v032"]=mod
spec.loader.exec_module(mod)

def a(c,m):
    if not c: raise AssertionError(m)

rules=(
    mod.ConditionRule("late-rate","late_delivery_rate",mod.ConditionOperator.GT,0.10),
    mod.ConditionRule("profit","monthly_profit",mod.ConditionOperator.GTE,5000),
)
batch=mod.evaluate_conditions(
    {"late_delivery_rate":0.18,"monthly_profit":6200},
    rules,
)
a(batch.any_matched is True,batch)
a(batch.all_matched is True,batch)
a(batch.monitoring_started is False,batch)
a(batch.notification_sent is False,batch)
print("condition evaluation: PASS")

missing=mod.evaluate_conditions({},(mod.ConditionRule("x","missing",mod.ConditionOperator.GT,1),))
a(missing.results[0].boundary==mod.ConditionBoundary.MISSING_METRIC,missing)
print("missing metric boundary: PASS")

duplicate=mod.evaluate_conditions(
    {"x":2},
    (
        mod.ConditionRule("same","x",mod.ConditionOperator.GT,1),
        mod.ConditionRule("same","x",mod.ConditionOperator.GT,1),
    ),
)
a(duplicate.results[1].boundary==mod.ConditionBoundary.INVALID_RULE,duplicate)
print("duplicate rule rejection: PASS")

many=tuple(mod.ConditionRule(f"r{i}","x",mod.ConditionOperator.GT,0) for i in range(10))
bounded=mod.evaluate_conditions({"x":1},many,max_rules=4)
a(len(bounded.results)==4,bounded)
a(bounded.rule_limit_enforced is False,bounded)
print("condition rule bound: PASS")

public=mod.public_condition_batch(batch)
a(public["monitoring_started"] is False,public)
a(public["notification_sent"] is False,public)
print("condition side-effect boundary: PASS")

print("SHY v0.32 EVENT & CONDITION INTELLIGENCE: PASS")

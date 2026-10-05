import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"services"/"agent-runtime"/"reliability_intelligence.py"
s=importlib.util.spec_from_file_location("r",P);r=importlib.util.module_from_spec(s);sys.modules["r"]=r;s.loader.exec_module(r)
def a(c,m):
    if not c: raise AssertionError(m)
high=r.evaluate_reliability(r.ReliabilityDimensions(.95,.94,.96,.9,.98));a(high.boundary==r.ReliabilityBoundary.PASS,high);a(high.confidence_cap>=.9,high);print("reliability pass: PASS")
rev=r.evaluate_reliability(r.ReliabilityDimensions(.8,.82,.75,.6,.95));a(rev.boundary==r.ReliabilityBoundary.REVISE,rev);a(rev.revision_recommended,rev);a(rev.max_revisions<=3,rev);print("bounded revise: PASS")
block=r.evaluate_reliability(r.ReliabilityDimensions(.95,.95,.95,.95,.5));a(block.boundary==r.ReliabilityBoundary.BLOCK,block);a(block.confidence_cap<=.35,block);print("safety block: PASS")
ins=r.evaluate_reliability(r.ReliabilityDimensions(.8,.6,.9,.9,.95),evidence_available=False);a(ins.boundary==r.ReliabilityBoundary.INSUFFICIENT_EVIDENCE,ins);a(ins.confidence_cap<=.55,ins);print("evidence boundary: PASS")
cal=r.aggregate_calibration((r.CalibrationSample(.9,True),r.CalibrationSample(.8,False),r.CalibrationSample(.99,True,False)))
a(cal.sample_count==2,cal);a(0<=cal.brier_score<=1,cal);print("verified calibration: PASS")
bounded=r.aggregate_calibration(tuple(r.CalibrationSample(.5,True) for _ in range(20)),max_samples=5);a(bounded.sample_count==5 and bounded.bounded is False,bounded);print("calibration bound: PASS")
print("SHY v0.28 RELIABILITY CHECKPOINT: PASS")

import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"services"/"agent-runtime"/"multimodal_intelligence.py"
spec=importlib.util.spec_from_file_location("shy_mm_v024",P)
mm=importlib.util.module_from_spec(spec); sys.modules["shy_mm_v024"]=mm; spec.loader.exec_module(mm)

def a(c,m):
    if not c: raise AssertionError(m)

items=(
    mm.build_evidence_unit(modality="TEXT",source_id="t1",content="Truck 12 is delayed",claims={"truck12_status":"delayed"}),
    mm.build_evidence_unit(modality="VOICE",source_id="v1",content="Truck 12 is delayed",claims={"truck12_status":"delayed"}),
    mm.build_evidence_unit(modality="VISION",source_id="i1",content="Dashboard shows delayed",claims={"truck12_status":"delayed"},provenance_available=True),
)
f=mm.fuse_evidence(items)
a(f.boundary==mm.FusionBoundary.FUSED,f)
a(f.modalities==("TEXT","VISION","VOICE"),f.modalities)
a(f.source_count==3,"source count")
a(not f.conflicts,"no conflict")
print("consistent multimodal fusion: PASS")

conflict=mm.fuse_evidence((
    mm.build_evidence_unit(modality="TEXT",source_id="t2",content="status active",claims={"status":"active"}),
    mm.build_evidence_unit(modality="VISION",source_id="i2",content="status stopped",claims={"status":"stopped"},provenance_available=True),
))
a(conflict.boundary==mm.FusionBoundary.CONFLICT_REQUIRES_CLARIFICATION,conflict)
a(len(conflict.conflicts)==1,"conflict count")
a(set(conflict.conflicts[0].modalities)=={"TEXT","VISION"},"conflict modality provenance")
print("cross-modality conflict: PASS")

try:
    mm.build_evidence_unit(modality="VISION",source_id="i3",content="x",provenance_available=False)
    raise AssertionError("vision without provenance should fail")
except ValueError as exc:
    a(str(exc)=="vision_provenance_required",str(exc))
print("vision provenance boundary: PASS")

dedup=mm.fuse_evidence((
    mm.build_evidence_unit(modality="TEXT",source_id="same",content="first"),
    mm.build_evidence_unit(modality="VOICE",source_id="same",content="duplicate"),
))
a(dedup.source_count==1,"duplicate source ids must dedup")
print("multimodal source dedup: PASS")

many=tuple(mm.build_evidence_unit(modality="TEXT",source_id=f"s{i}",content=str(i)) for i in range(20))
bounded=mm.fuse_evidence(many,max_sources=5)
a(bounded.source_count==5,"source bound")
a(bounded.max_sources_enforced is False,"truncation signal")
print("multimodal source bound: PASS")

empty=mm.fuse_evidence(())
a(empty.boundary==mm.FusionBoundary.DATA_REQUIRED,"empty evidence boundary")
print("multimodal missing-data boundary: PASS")

public=mm.public_fusion_metadata(conflict)
a(public["boundary"]=="CONFLICT_REQUIRES_CLARIFICATION","public boundary")
a("content" not in public["evidence"][0],"public metadata should not echo evidence content")
print("public multimodal metadata privacy: PASS")

print("SHY v0.24 MULTIMODAL CHECKPOINT: PASS")

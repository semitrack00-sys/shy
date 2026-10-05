import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "services" / "agent-runtime" / "vision_intelligence.py"

spec = importlib.util.spec_from_file_location("shy_vision_v023", MODULE_PATH)
vision = importlib.util.module_from_spec(spec)
sys.modules["shy_vision_v023"] = vision
spec.loader.exec_module(vision)


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


describe = vision.plan_visual_analysis(
    "Describe this image",
    has_image=True,
    provider_available=True,
)
_assert(describe.boundary == vision.VisionBoundary.ANALYZE, "available image/provider should permit analysis")
_assert(describe.identity_recognition_allowed is False, "identity recognition must remain disabled")
print("vision describe boundary: PASS")


missing_image = vision.plan_visual_analysis(
    "Read the text in this screenshot",
    has_image=False,
    provider_available=True,
)
_assert(missing_image.boundary == vision.VisionBoundary.IMAGE_REQUIRED, "missing image must be explicit")
print("vision image-required boundary: PASS")


missing_provider = vision.plan_visual_analysis(
    "Read the text in this screenshot",
    has_image=True,
    provider_available=False,
)
_assert(missing_provider.boundary == vision.VisionBoundary.PROVIDER_REQUIRED, "missing provider must be explicit")
print("vision provider-required boundary: PASS")


identity = vision.plan_visual_analysis(
    "Who is this person?",
    has_image=True,
    provider_available=True,
)
_assert(identity.task == vision.VisualTask.IDENTITY, "identity request should be classified")
_assert(identity.boundary == vision.VisionBoundary.DENIED, "real-person identity recognition must be denied")
_assert(identity.reason == "real_person_identity_recognition_not_supported", "identity denial reason mismatch")
print("real-person identity boundary: PASS")


accepted = vision.validate_visual_observation(
    source_id="img-001",
    provider="approved-vision",
    mime_type="image/png",
    width=1440,
    height=900,
    summary="A browser window with a settings panel.",
    extracted_text="Settings Account Security",
    labels=("browser", "settings"),
    regions=(
        {"label": "Settings button", "confidence": 0.94, "bbox": [0.1, 0.2, 0.3, 0.4]},
    ),
    provenance_available=True,
)
_assert(accepted.accepted is True and accepted.observation is not None, "valid observation should be accepted")
_assert(accepted.observation.regions[0].confidence == 0.94, "region confidence should be preserved")
print("visual observation validation: PASS")


no_provenance = vision.validate_visual_observation(
    source_id="img-002",
    provider="approved-vision",
    mime_type="image/jpeg",
    width=100,
    height=100,
    summary="test",
    provenance_available=False,
)
_assert(no_provenance.accepted is False, "visual observation without provenance must be rejected")
_assert(no_provenance.rejected_reason == "visual_provenance_required", "provenance rejection reason mismatch")
print("visual provenance requirement: PASS")


bad_type = vision.validate_visual_observation(
    source_id="img-003",
    provider="approved-vision",
    mime_type="application/pdf",
    width=100,
    height=100,
)
_assert(bad_type.accepted is False and bad_type.rejected_reason == "unsupported_image_type", "unsupported type must reject")
print("visual type boundary: PASS")


too_large = vision.validate_visual_observation(
    source_id="img-004",
    provider="approved-vision",
    mime_type="image/png",
    width=25000,
    height=200,
)
_assert(too_large.accepted is False and too_large.rejected_reason == "dimensions_exceed_limit", "oversize image must reject")
print("visual size boundary: PASS")


public = vision.public_visual_observation(accepted.observation)
_assert(public["identity_inference_performed"] is False, "public observation must state identity inference was not performed")
_assert(public["provider"] == "approved-vision", "public observation must preserve provider provenance")
print("public vision provenance: PASS")


print("SHY v0.23 VISION CHECKPOINT: PASS")

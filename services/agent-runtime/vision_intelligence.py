from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Sequence


class VisualTask(str, Enum):
    DESCRIBE = "DESCRIBE"
    READ_TEXT = "READ_TEXT"
    UI_INSPECTION = "UI_INSPECTION"
    DOCUMENT = "DOCUMENT"
    OBJECTS = "OBJECTS"
    QUESTION_ANSWER = "QUESTION_ANSWER"
    IDENTITY = "IDENTITY"


class VisionBoundary(str, Enum):
    ANALYZE = "ANALYZE"
    PROVIDER_REQUIRED = "PROVIDER_REQUIRED"
    IMAGE_REQUIRED = "IMAGE_REQUIRED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    DENIED = "DENIED"


class VisionSensitivity(str, Enum):
    LOW = "LOW"
    SENSITIVE = "SENSITIVE"


@dataclass(frozen=True)
class VisionPlan:
    task: VisualTask
    boundary: VisionBoundary
    requires_image: bool
    requires_provider: bool
    identity_recognition_allowed: bool
    sensitivity: VisionSensitivity
    reason: str


@dataclass(frozen=True)
class VisualRegion:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class VisualObservation:
    source_id: str
    provider: str
    mime_type: str
    width: int
    height: int
    summary: str
    extracted_text: str
    labels: tuple[str, ...]
    regions: tuple[VisualRegion, ...]
    contains_people: bool
    provenance_available: bool


@dataclass(frozen=True)
class ObservationValidation:
    accepted: bool
    observation: VisualObservation | None
    rejected_reason: str | None


_IDENTITY_PATTERNS = (
    "who is this",
    "who is in this",
    "identify this person",
    "identify the person",
    "what is this person's name",
    "what is this persons name",
    "name this person",
    "recognize this person",
    "facial recognition",
)

_TEXT_PATTERNS = (
    "read the text",
    "what does this say",
    "ocr",
    "read this document",
    "read this screenshot",
)

_UI_PATTERNS = (
    "screen",
    "screenshot",
    "button",
    "menu",
    "dialog",
    "ui",
    "interface",
)

_DOCUMENT_PATTERNS = (
    "document",
    "invoice",
    "receipt",
    "form",
    "page",
)

_OBJECT_PATTERNS = (
    "what objects",
    "what is in the image",
    "what is in this image",
    "describe the objects",
)

_SENSITIVE_VISUAL_MARKERS = (
    "password",
    "credit card",
    "social security",
    "ssn",
    "passport",
    "driver license",
    "medical record",
    "bank account",
    "secret",
    "api key",
    "token",
)

_ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def classify_visual_task(prompt: str) -> VisualTask:
    text = _normalize(prompt)

    if any(marker in text for marker in _IDENTITY_PATTERNS):
        return VisualTask.IDENTITY
    if any(marker in text for marker in _TEXT_PATTERNS):
        return VisualTask.READ_TEXT
    if any(marker in text for marker in _UI_PATTERNS):
        return VisualTask.UI_INSPECTION
    if any(marker in text for marker in _DOCUMENT_PATTERNS):
        return VisualTask.DOCUMENT
    if any(marker in text for marker in _OBJECT_PATTERNS):
        return VisualTask.OBJECTS
    if "?" in str(prompt or ""):
        return VisualTask.QUESTION_ANSWER
    return VisualTask.DESCRIBE


def plan_visual_analysis(
    prompt: str,
    *,
    has_image: bool,
    provider_available: bool,
) -> VisionPlan:
    task = classify_visual_task(prompt)
    text = _normalize(prompt)
    sensitivity = (
        VisionSensitivity.SENSITIVE
        if any(marker in text for marker in _SENSITIVE_VISUAL_MARKERS)
        else VisionSensitivity.LOW
    )

    if task == VisualTask.IDENTITY:
        return VisionPlan(
            task=task,
            boundary=VisionBoundary.DENIED,
            requires_image=True,
            requires_provider=False,
            identity_recognition_allowed=False,
            sensitivity=sensitivity,
            reason="real_person_identity_recognition_not_supported",
        )

    if not has_image:
        return VisionPlan(
            task=task,
            boundary=VisionBoundary.IMAGE_REQUIRED,
            requires_image=True,
            requires_provider=not provider_available,
            identity_recognition_allowed=False,
            sensitivity=sensitivity,
            reason="image_required",
        )

    if not provider_available:
        return VisionPlan(
            task=task,
            boundary=VisionBoundary.PROVIDER_REQUIRED,
            requires_image=True,
            requires_provider=True,
            identity_recognition_allowed=False,
            sensitivity=sensitivity,
            reason="vision_provider_required",
        )

    return VisionPlan(
        task=task,
        boundary=VisionBoundary.ANALYZE,
        requires_image=True,
        requires_provider=False,
        identity_recognition_allowed=False,
        sensitivity=sensitivity,
        reason="vision_analysis_allowed",
    )


def _clean_text(value: str, max_chars: int) -> str:
    normalized = " ".join(str(value or "").strip().split())
    return normalized[: max(0, int(max_chars))]


def _valid_bbox(value: Sequence[float] | None) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if len(value) != 4:
        return None
    coords = tuple(float(item) for item in value)
    if any(item < 0.0 or item > 1.0 for item in coords):
        return None
    left, top, right, bottom = coords
    if right < left or bottom < top:
        return None
    return coords


def validate_visual_observation(
    *,
    source_id: str,
    provider: str,
    mime_type: str,
    width: int,
    height: int,
    summary: str = "",
    extracted_text: str = "",
    labels: Sequence[str] = (),
    regions: Sequence[dict] = (),
    contains_people: bool = False,
    provenance_available: bool = True,
) -> ObservationValidation:
    source_id = str(source_id or "").strip()
    provider = str(provider or "").strip()
    mime_type = str(mime_type or "").strip().lower()

    if not source_id:
        return ObservationValidation(False, None, "source_id_required")
    if not provider:
        return ObservationValidation(False, None, "provider_required")
    if mime_type not in _ALLOWED_MIME_TYPES:
        return ObservationValidation(False, None, "unsupported_image_type")
    if int(width) <= 0 or int(height) <= 0:
        return ObservationValidation(False, None, "invalid_dimensions")
    if int(width) > 20000 or int(height) > 20000:
        return ObservationValidation(False, None, "dimensions_exceed_limit")
    if not provenance_available:
        return ObservationValidation(False, None, "visual_provenance_required")

    clean_labels = tuple(
        item
        for item in (
            _clean_text(label, 120)
            for label in labels[:64]
        )
        if item
    )

    clean_regions: list[VisualRegion] = []
    for raw in regions[:64]:
        if not isinstance(raw, dict):
            continue
        label = _clean_text(raw.get("label", ""), 120)
        if not label:
            continue
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
        bbox = _valid_bbox(raw.get("bbox"))
        clean_regions.append(
            VisualRegion(
                label=label,
                confidence=round(confidence, 6),
                bbox=bbox,
            )
        )

    observation = VisualObservation(
        source_id=source_id,
        provider=provider,
        mime_type=mime_type,
        width=int(width),
        height=int(height),
        summary=_clean_text(summary, 4000),
        extracted_text=_clean_text(extracted_text, 12000),
        labels=clean_labels,
        regions=tuple(clean_regions),
        contains_people=bool(contains_people),
        provenance_available=True,
    )
    return ObservationValidation(True, observation, None)


def public_vision_plan(plan: VisionPlan) -> dict[str, object]:
    return {
        "task": plan.task.value,
        "boundary": plan.boundary.value,
        "requires_image": plan.requires_image,
        "requires_provider": plan.requires_provider,
        "identity_recognition_allowed": plan.identity_recognition_allowed,
        "sensitivity": plan.sensitivity.value,
        "reason": plan.reason,
    }


def public_visual_observation(observation: VisualObservation) -> dict[str, object]:
    return {
        "source_id": observation.source_id,
        "provider": observation.provider,
        "mime_type": observation.mime_type,
        "width": observation.width,
        "height": observation.height,
        "summary": observation.summary,
        "extracted_text": observation.extracted_text,
        "labels": list(observation.labels),
        "regions": [
            {
                "label": region.label,
                "confidence": region.confidence,
                "bbox": list(region.bbox) if region.bbox is not None else None,
            }
            for region in observation.regions
        ],
        "contains_people": observation.contains_people,
        "provenance_available": observation.provenance_available,
        "identity_inference_performed": False,
    }

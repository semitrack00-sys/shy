from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class ReliabilityBoundary(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    BLOCK = "BLOCK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class ReliabilityDimensions:
    correctness: float
    grounding: float
    consistency: float
    completeness: float
    safety: float


@dataclass(frozen=True)
class ReliabilityReport:
    quality_score: float
    boundary: ReliabilityBoundary
    confidence_cap: float
    revision_recommended: bool
    max_revisions: int
    weak_dimensions: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationSample:
    predicted_confidence: float
    success: bool
    verified: bool = True


@dataclass(frozen=True)
class CalibrationReport:
    sample_count: int
    average_confidence: float
    observed_accuracy: float
    calibration_gap: float
    brier_score: float
    bounded: bool


def _unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def evaluate_reliability(
    dimensions: ReliabilityDimensions,
    *,
    evidence_available: bool = True,
    max_revisions: int = 2,
) -> ReliabilityReport:
    values = {
        "correctness": _unit(dimensions.correctness),
        "grounding": _unit(dimensions.grounding),
        "consistency": _unit(dimensions.consistency),
        "completeness": _unit(dimensions.completeness),
        "safety": _unit(dimensions.safety),
    }
    weights = {
        "correctness": 0.30,
        "grounding": 0.25,
        "consistency": 0.20,
        "completeness": 0.10,
        "safety": 0.15,
    }
    quality = sum(values[name] * weights[name] for name in weights)
    weak = tuple(sorted(name for name, value in values.items() if value < 0.70))

    if values["safety"] < 0.80:
        boundary = ReliabilityBoundary.BLOCK
    elif not evidence_available and (values["grounding"] < 0.85 or values["correctness"] < 0.85):
        boundary = ReliabilityBoundary.INSUFFICIENT_EVIDENCE
    elif quality >= 0.85 and not weak:
        boundary = ReliabilityBoundary.PASS
    else:
        boundary = ReliabilityBoundary.REVISE

    confidence_cap = min(values["correctness"], values["grounding"], values["consistency"])
    if boundary == ReliabilityBoundary.BLOCK:
        confidence_cap = min(confidence_cap, 0.35)
    elif boundary == ReliabilityBoundary.INSUFFICIENT_EVIDENCE:
        confidence_cap = min(confidence_cap, 0.55)
    elif boundary == ReliabilityBoundary.REVISE:
        confidence_cap = min(confidence_cap, 0.75)

    bounded_revisions = max(0, min(int(max_revisions), 3))
    return ReliabilityReport(
        quality_score=round(_unit(quality), 6),
        boundary=boundary,
        confidence_cap=round(_unit(confidence_cap), 6),
        revision_recommended=boundary == ReliabilityBoundary.REVISE and bounded_revisions > 0,
        max_revisions=bounded_revisions,
        weak_dimensions=weak,
    )


def aggregate_calibration(
    samples: Sequence[CalibrationSample],
    *,
    max_samples: int = 500,
) -> CalibrationReport:
    bound = max(1, min(int(max_samples), 5000))
    verified = [item for item in samples if item.verified][:bound]
    if not verified:
        return CalibrationReport(0, 0.0, 0.0, 0.0, 0.0, len(samples) <= bound)

    confidences = [_unit(item.predicted_confidence) for item in verified]
    outcomes = [1.0 if item.success else 0.0 for item in verified]
    avg_conf = sum(confidences) / len(confidences)
    accuracy = sum(outcomes) / len(outcomes)
    brier = sum((c - o) ** 2 for c, o in zip(confidences, outcomes)) / len(outcomes)

    return CalibrationReport(
        sample_count=len(verified),
        average_confidence=round(avg_conf, 6),
        observed_accuracy=round(accuracy, 6),
        calibration_gap=round(abs(avg_conf - accuracy), 6),
        brier_score=round(brier, 6),
        bounded=len(samples) <= bound,
    )


def public_reliability_report(report: ReliabilityReport) -> dict[str, object]:
    return {
        "quality_score": report.quality_score,
        "boundary": report.boundary.value,
        "confidence_cap": report.confidence_cap,
        "revision_recommended": report.revision_recommended,
        "max_revisions": report.max_revisions,
        "weak_dimensions": list(report.weak_dimensions),
    }


def public_calibration_report(report: CalibrationReport) -> dict[str, object]:
    return {
        "sample_count": report.sample_count,
        "average_confidence": report.average_confidence,
        "observed_accuracy": report.observed_accuracy,
        "calibration_gap": report.calibration_gap,
        "brier_score": report.brier_score,
        "bounded": report.bounded,
    }

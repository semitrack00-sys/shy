"""Deterministic ranking of explicitly supplied numeric options; no fact gathering."""
from decimal import Decimal, localcontext
import re
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DECIMAL = re.compile(r"[+-]?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z")


class StrictInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Criterion(StrictInput):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,23}$")
    name: str = Field(min_length=1, max_length=80)
    unit: str = Field(default="", max_length=24)
    direction: Literal["maximize", "minimize"]
    weight: str = Field(max_length=24)

    @field_validator("weight")
    @classmethod
    def valid_weight(cls, value):
        if not DECIMAL.fullmatch(value) or not Decimal("0") < Decimal(value) <= Decimal("100"):
            raise ValueError("weight must be an explicit decimal greater than zero and at most 100")
        return value


class Option(StrictInput):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,23}$")
    name: str = Field(min_length=1, max_length=80)
    values: dict[str, str] = Field(min_length=1, max_length=6)

    @field_validator("values")
    @classmethod
    def valid_values(cls, values):
        if any(not DECIMAL.fullmatch(value) for value in values.values()):
            raise ValueError("values must be decimal strings with at most 12 integer and 8 fractional digits")
        return values


class ComparisonRequest(StrictInput):
    criteria: list[Criterion] = Field(min_length=1, max_length=6)
    options: list[Option] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def consistent_inputs(self):
        ids = {item.id for item in self.criteria}
        if len(ids) != len(self.criteria) or len({item.id for item in self.options}) != len(self.options):
            raise ValueError("criterion and option IDs must be unique within each list")
        if any(set(item.values) != ids for item in self.options):
            raise ValueError("every option must supply exactly every criterion; missing values are not guessed")
        for label in [item.name for item in self.criteria + self.options] + [item.unit for item in self.criteria]:
            if (not label.strip() and label != "") or any(ord(char) < 32 or ord(char) == 127 for char in label):
                raise ValueError("labels must be single-line text")
        return self


def compare_options(request: ComparisonRequest) -> dict:
    with localcontext() as ctx:
        ctx.prec = 40
        weights = [Decimal(c.weight) for c in request.criteria]
        columns = [[Decimal(o.values[c.id]) for o in request.options] for c in request.criteria]
        utilities = []
        for criterion, values in zip(request.criteria, columns):
            low, high = min(values), max(values)
            utilities.append([Decimal("0.5") if low == high else
                              (v - low) / (high - low) if criterion.direction == "maximize" else
                              (high - v) / (high - low) for v in values])
        scores = [(sum(w * col[i] for w, col in zip(weights, utilities)) / sum(weights) * 100)
                  .quantize(Decimal("0.000001")) for i in range(len(request.options))]
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        rows = []
        for i in order:
            dominated = []
            for j in range(len(request.options)):
                if i == j:
                    continue
                differences = [(col[j] - col[i]) * (1 if c.direction == "maximize" else -1)
                               for c, col in zip(request.criteria, columns)]
                if all(d >= 0 for d in differences) and any(d > 0 for d in differences):
                    dominated.append(request.options[j].id)
            rows.append({"id": request.options[i].id, "name": request.options[i].name,
                         "score": str(scores[i]), "rank": 1 + sum(s > scores[i] for s in scores),
                         "values": request.options[i].values, "dominated_by": dominated})
    return {"method": "weighted_min_max", "criteria": [c.model_dump() for c in request.criteria],
            "ranking": rows, "highest_scored_ids": [r["id"] for r in rows if r["rank"] == 1],
            "score_decimals": 6, "equal_column_utility": "0.5", "facts_verified": False,
            "model_invoked": False, "external_execution": False}


def _plain(value: str) -> str:
    # Escape every Markdown punctuation character; labels cannot become links or tables.
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|~-])", r"\\\1", value)


def comparison_message(result: dict) -> str:
    criteria = result["criteria"]
    lines = ["Comparison using your supplied values and weights.", "",
             "Scores use weighted min/max normalization across these options (0–100). Equal columns contribute 0.5. Scores round to six decimal places; equal displayed scores tie. Changing options or weights can change the ranking. Units are labels; no conversion or missing-value inference occurs.", "",
             "Criteria:"]
    lines += [f"- {_plain(c['name'])}: {c['direction']}, weight {c['weight']}, unit {_plain(c['unit']) or 'unspecified'}." for c in criteria]
    lines += ["", "| Rank | Option | Score | Supplied values |", "| --- | --- | --- | --- |"]
    for row in result["ranking"]:
        values = "; ".join(f"{_plain(c['name'])}: {row['values'][c['id']]} {_plain(c['unit'])}" for c in criteria)
        lines.append(f"| {row['rank']} | {_plain(row['name'])} | {row['score']} | {values} |")
    lines += ["", "The highest score reflects these criteria and inputs, not independently verified quality or a universal recommendation."]
    return "\n".join(lines)


router = APIRouter(prefix="/comparisons", tags=["Supplied option comparisons"])


@router.post("/evaluate")
def evaluate(request: ComparisonRequest):
    result = compare_options(request)
    return {**result, "message": comparison_message(result)}

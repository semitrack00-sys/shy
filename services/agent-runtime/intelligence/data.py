from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from .common import canonical, integer, number, numeric_values, percentile, rows, text, timestamp


def kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (float, int)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "object" if isinstance(value, dict) else "array"


def columns(items):
    names = sorted({name for item in items for name in item})
    if len(names) > 100:
        raise ValueError("column_limit_exceeded")
    return names


def profile_schema(p: dict) -> dict:
    items = rows(p, "rows")
    result = []
    for column in columns(items):
        counts = Counter(kind(item.get(column)) for item in items)
        result.append({"column": column, "types": dict(counts), "mixed_non_null_types": len(set(counts) - {"null"}) > 1})
    return {"row_count": len(items), "columns": result}


def descriptive_stats(p: dict) -> dict:
    values = numeric_values(p)
    return {"count": len(values), "min": min(values), "max": max(values), "mean": statistics.fmean(values), "median": statistics.median(values), "population_stddev": statistics.pstdev(values), "q1": percentile(values, 0.25), "q3": percentile(values, 0.75)}


def detect_outliers(p: dict) -> dict:
    values = numeric_values(p)
    threshold = number(p.get("threshold", 3.5), "threshold", 0)
    if threshold == 0:
        raise ValueError("positive_threshold_required")
    median = statistics.median(values)
    mad = statistics.median(abs(x - median) for x in values)
    # A zero MAD needs special handling; differing observations still deserve review.
    indices = [i for i, x in enumerate(values) if (abs(x - median) > 0 if mad == 0 else 0.67448975 * abs(x - median) / mad > threshold)]
    return {"indices": indices, "median": median, "mad": mad, "method": "modified_z_score" if mad else "zero_mad_deviation", "outliers_removed": False}


def missing_report(p: dict) -> dict:
    items = rows(p, "rows")
    report = []
    for column in columns(items):
        missing = [i for i, item in enumerate(items) if item.get(column) is None or item.get(column) == ""]
        report.append({"column": column, "missing_count": len(missing), "missing_fraction": len(missing) / len(items), "row_indices": missing})
    return {"columns": report, "row_count": len(items), "imputation_applied": False}


def key_columns(p: dict, key: str = "keys") -> list[str]:
    keys = p.get(key)
    if not isinstance(keys, list) or not keys or any(not isinstance(x, str) or not x for x in keys) or len(set(keys)) != len(keys):
        raise ValueError(f"{key}_must_be_unique_column_names")
    return keys


def row_key(item: dict, keys: list[str]) -> str:
    if any(key not in item or item[key] is None for key in keys):
        raise ValueError("key_column_missing_or_null")
    return canonical([item[key] for key in keys])


def deduplicate_rows(p: dict) -> dict:
    items = rows(p, "rows")
    keys = key_columns(p)
    seen, keep, duplicates = {}, [], []
    conflicts = []
    for index, item in enumerate(items):
        key = row_key(item, keys)
        if key in seen:
            duplicates.append(index)
            if canonical(item) != canonical(items[seen[key]]):
                conflicts.append({"kept_index": seen[key], "duplicate_index": index})
        else:
            seen[key] = index
            keep.append(item)
    return {"rows": keep, "duplicate_indices": duplicates, "conflicts": conflicts, "persistent_change_applied": False}


def join_rows(p: dict) -> dict:
    left, right = rows(p, "left"), rows(p, "right")
    keys = key_columns(p)
    mode = p.get("mode", "inner")
    if mode not in {"inner", "left"}:
        raise ValueError("unsupported_join_mode")
    right_index = defaultdict(list)
    for item in right:
        right_index[row_key(item, keys)].append(item)
    result = []
    for item in left:
        matches = right_index.get(row_key(item, keys), [])
        for match in matches:
            # Preserve both sides explicitly so colliding column names cannot overwrite evidence.
            result.append({"left": item, "right": match})
        if not matches and mode == "left":
            result.append({"left": item, "right": None})
        if len(result) > 500:
            raise ValueError("join_output_limit_exceeded")
    return {"rows": result, "row_count": len(result), "mode": mode}


def aggregate_rows(p: dict) -> dict:
    items = rows(p, "rows")
    keys = key_columns(p, "group_by")
    column = text(p.get("value_column"), "value_column")
    groups, labels = defaultdict(list), {}
    for item in items:
        key = row_key(item, keys)
        labels[key] = {x: item[x] for x in keys}
        groups[key].append(number(item.get(column), column))
    result = [{"group": labels[key], "count": len(values), "sum": sum(values), "mean": statistics.fmean(values), "min": min(values), "max": max(values)} for key, values in sorted(groups.items())]
    return {"groups": result}


def transform_rows(p: dict) -> dict:
    items = rows(p, "rows")
    transforms = rows(p, "transforms")
    result = [dict(x) for x in items]
    for transform in transforms:
        column = text(transform.get("column"), "column")
        operation = text(transform.get("operation"), "operation")
        if operation not in {"scale", "round", "uppercase", "strip", "iso_date"}:
            raise ValueError("unsupported_transform")
        for item in result:
            if column not in item:
                raise ValueError("transform_column_missing")
            value = item[column]
            if operation == "scale":
                item[column] = number(value, column) * number(transform.get("factor"), "factor")
            elif operation == "round":
                item[column] = round(number(value, column), integer(transform.get("digits", 2), "digits", 0, 10))
            elif operation == "uppercase":
                item[column] = text(value, column).upper()
            elif operation == "strip":
                item[column] = text(value, column).strip()
            else:
                item[column] = timestamp(value, column).isoformat()
    return {"rows": result, "persistent_change_applied": False}


def compare_snapshots(p: dict) -> dict:
    before, after = rows(p, "before", allow_empty=True), rows(p, "after", allow_empty=True)
    keys = key_columns(p)
    def index(items):
        result = {row_key(x, keys): x for x in items}
        if len(result) != len(items):
            raise ValueError("snapshot_duplicate_key")
        return result
    old, new = index(before), index(after)
    return {"added": [new[x] for x in sorted(new.keys() - old.keys())], "removed": [old[x] for x in sorted(old.keys() - new.keys())], "changed": [{"before": old[x], "after": new[x]} for x in sorted(old.keys() & new.keys()) if canonical(old[x]) != canonical(new[x])]}


def data_quality(p: dict) -> dict:
    items = rows(p, "rows")
    rules = rows(p, "rules")
    failures = []
    for rule in rules:
        column = text(rule.get("column"), "column")
        check = text(rule.get("check"), "check")
        if check not in {"required", "unique", "numeric_range", "enum"}:
            raise ValueError("unsupported_quality_check")
        allowed = rule.get("values", [])
        if check == "enum" and (not isinstance(allowed, list) or not allowed):
            raise ValueError("enum_values_required")
        if check == "numeric_range":
            low, high = number(rule.get("min")), number(rule.get("max"))
            if low > high:
                raise ValueError("invalid_numeric_range")
        seen = set()
        for i, item in enumerate(items):
            value = item.get(column)
            if check == "required":
                ok = column in item and value is not None and value != ""
            elif check == "unique":
                key = canonical(value)
                ok = column in item and value is not None and key not in seen
                seen.add(key)
            elif check == "enum":
                ok = column in item and canonical(value) in {canonical(x) for x in allowed}
            else:
                ok = isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high
            if not ok:
                failures.append({"row_index": i, "column": column, "check": check})
                if len(failures) > 500:
                    raise ValueError("quality_failure_limit_exceeded")
    return {"passed": not failures, "failures": failures, "checks_run": len(items) * len(rules), "rows_modified": False}


CAPABILITIES = (
    (71, "profile_schema", profile_schema), (72, "descriptive_stats", descriptive_stats),
    (73, "detect_outliers", detect_outliers), (74, "missing_report", missing_report),
    (75, "deduplicate_rows", deduplicate_rows), (76, "join_rows", join_rows),
    (77, "aggregate_rows", aggregate_rows), (78, "transform_rows", transform_rows),
    (79, "compare_snapshots", compare_snapshots), (80, "data_quality", data_quality),
)

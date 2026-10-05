from __future__ import annotations

from collections import defaultdict, deque

from .common import digest, integer, number, rows, text, timestamp, unique_ids


def graph(p: dict) -> tuple[dict, list[str], dict]:
    tasks = rows(p, "tasks")
    unique_ids(tasks)
    index = {x["id"]: x for x in tasks}
    children = defaultdict(list)
    indegree = {}
    for item in tasks:
        dependencies = item.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(x, str) for x in dependencies) or len(set(dependencies)) != len(dependencies):
            raise ValueError("invalid_dependencies")
        if any(x not in index for x in dependencies):
            raise ValueError("unknown_dependency")
        number(item.get("duration", 1), "duration", 0)
        indegree[item["id"]] = len(dependencies)
        for dependency in dependencies:
            children[dependency].append(item["id"])
    ready = deque(sorted(x for x in index if not indegree[x]))
    order = []
    while ready:
        current = ready.popleft()
        order.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if len(order) != len(index):
        raise ValueError("dependency_cycle")
    return index, order, children


def schedule_tasks(p: dict) -> dict:
    index, order, _ = graph(p)
    ends, schedule = {}, []
    for identifier in order:
        task = index[identifier]
        start = max((ends[x] for x in task.get("dependencies", [])), default=0)
        end = start + number(task.get("duration", 1), "duration", 0)
        ends[identifier] = end
        schedule.append({"id": identifier, "start": start, "end": end})
    return {"schedule": schedule, "makespan": max(ends.values()), "resource_constraints_applied": False}


def critical_path(p: dict) -> dict:
    index, order, children = graph(p)
    schedule = schedule_tasks(p)
    timings = {x["id"]: x for x in schedule["schedule"]}
    latest, result = {}, []
    for identifier in reversed(order):
        end = min((latest[x] for x in children[identifier]), default=schedule["makespan"])
        latest[identifier] = end - number(index[identifier].get("duration", 1), "duration", 0)
    for identifier in order:
        slack = latest[identifier] - timings[identifier]["start"]
        result.append({"id": identifier, "slack": round(slack, 8), "critical": abs(slack) < 1e-8})
    return {"tasks": result, "makespan": schedule["makespan"]}


def verify_checkpoint(p: dict) -> dict:
    checkpoint = p.get("checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint_required")
    expected = text(p.get("sha256"), "sha256")
    computed = digest(checkpoint)
    return {"integrity_matches": computed == expected, "computed_sha256": computed, "authenticity_verified": False, "restored": False}


def retry_policy(p: dict) -> dict:
    attempt = integer(p.get("attempt", 0), "attempt", 0, 30)
    maximum = integer(p.get("max_attempts", 3), "max_attempts", 1, 30)
    base = number(p.get("base_seconds", 1), "base_seconds", 0)
    cap = number(p.get("cap_seconds", 60), "cap_seconds", 0)
    failure = text(p.get("failure"), "failure")
    safe = p.get("idempotent") is True or p.get("idempotency_key_bound") is True
    retry = failure in {"timeout", "rate_limit", "unavailable"} and safe and attempt < maximum
    delay = min(cap, base * (2**attempt))
    if p.get("retry_after") is not None:
        # Server-directed delays are honored even when they exceed exponential-backoff cap.
        delay = max(delay, number(p["retry_after"], "retry_after", 0))
    return {"retry": retry, "delay_seconds": delay if retry else None, "reason": "transient_safe_retry" if retry else "terminal_unsafe_or_exhausted", "retry_executed": False}


def idempotency_fingerprint(p: dict) -> dict:
    scope = text(p.get("scope"), "scope")
    operation = text(p.get("operation"), "operation")
    if not isinstance(p.get("arguments"), dict):
        raise ValueError("arguments_required")
    fingerprint = digest({"scope": scope, "operation": operation, "arguments": p["arguments"]})
    return {"fingerprint": fingerprint, "deduplication_persisted": False, "exactly_once_execution_guaranteed": False}


def allocate_budget(p: dict) -> dict:
    total = number(p.get("total"), "total", 0)
    tasks = rows(p, "tasks")
    unique_ids(tasks)
    minimum = sum(number(x.get("minimum", 0), "minimum", 0) for x in tasks)
    if minimum > total:
        return {"feasible": False, "shortfall": minimum - total, "allocations": []}
    weights = [number(x.get("weight", 1), "weight", 0) for x in tasks]
    weight_sum = sum(weights)
    if not weight_sum:
        raise ValueError("positive_weight_required")
    allocations = [{"id": x["id"], "amount": number(x.get("minimum", 0), "minimum", 0) + (total - minimum) * w / weight_sum} for x, w in zip(tasks, weights)]
    return {"feasible": True, "allocations": allocations, "total": total}


def cancellation_plan(p: dict) -> dict:
    index, order, children = graph(p)
    target = text(p.get("target"), "target")
    if target not in index:
        raise ValueError("unknown_target")
    affected = {target}
    queue = deque([target])
    while queue:
        for child in children[queue.popleft()]:
            if child not in affected:
                affected.add(child)
                queue.append(child)
    return {"affected_ids": [x for x in reversed(order) if x in affected], "unaffected_ids": [x for x in order if x not in affected], "cancelled": False}


def approval_binding(p: dict) -> dict:
    request = p.get("request")
    approval = p.get("approval")
    if not isinstance(request, dict) or not isinstance(approval, dict):
        raise ValueError("request_and_approval_required")
    now = timestamp(p.get("now"), "now")
    expires = timestamp(approval.get("expires_at"), "expires_at")
    matching = approval.get("request_sha256") == digest(request)
    return {"request_matches": matching, "expired": expires <= now, "eligible_for_gateway_verification": matching and expires > now, "approval_authenticated": False, "authorization_granted": False}


def recovery_plan(p: dict) -> dict:
    index, order, children = graph(p)
    completed = p.get("completed", [])
    failed = p.get("failed", [])
    if not isinstance(completed, list) or not isinstance(failed, list) or any(not isinstance(x, str) or x not in index for x in completed + failed):
        raise ValueError("unknown_or_invalid_recovery_task")
    if set(completed) & set(failed):
        raise ValueError("completed_failed_conflict")
    for identifier in completed:
        if any(x not in completed for x in index[identifier].get("dependencies", [])):
            raise ValueError("completed_dependency_missing")
    invalidated = set(failed)
    for identifier in order:
        if any(x in invalidated for x in index[identifier].get("dependencies", [])):
            invalidated.add(identifier)
    preserved = set(completed) - invalidated
    retry = [x for x in order if x not in preserved]
    unsafe = [x for x in retry if index[x].get("side_effects") is True and index[x].get("idempotent") is not True]
    return {"preserved_ids": sorted(preserved), "resume_ids": retry, "requires_gateway_review": unsafe, "resumed": False}


def dry_run(p: dict) -> dict:
    actions = rows(p, "actions")
    unique_ids(actions)
    allow = p.get("allowed_operations", [])
    if not isinstance(allow, list) or any(not isinstance(x, str) for x in allow):
        raise ValueError("allowed_operations_must_be_strings")
    report = []
    for item in actions:
        operation = text(item.get("operation"), "operation")
        if not isinstance(item.get("side_effects"), bool):
            raise ValueError("side_effects_must_be_boolean")
        allowed = operation in allow
        report.append({"id": item["id"], "decision": "review_required" if allowed and item["side_effects"] else "eligible_for_read_only_gateway" if allowed else "denied"})
    return {"actions": report, "execution_performed": False, "authorization_granted": False}


CAPABILITIES = (
    (61, "schedule_tasks", schedule_tasks), (62, "critical_path", critical_path),
    (63, "verify_checkpoint", verify_checkpoint), (64, "retry_policy", retry_policy),
    (65, "idempotency_fingerprint", idempotency_fingerprint), (66, "allocate_budget", allocate_budget),
    (67, "cancellation_plan", cancellation_plan), (68, "approval_binding", approval_binding),
    (69, "recovery_plan", recovery_plan), (70, "dry_run", dry_run),
)

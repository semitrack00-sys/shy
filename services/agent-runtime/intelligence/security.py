from __future__ import annotations

import ipaddress
import re
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

from .common import digest, rows, text, unique_ids
from .workflows import graph


def injection_scan(p: dict) -> dict:
    value = text(p.get("text"))
    patterns = {
        "override_instructions": r"(?i)(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|rules|prompts)",
        "role_spoofing": r"(?i)(?:<\|(?:system|developer)\|>|\[/?INST\]|\bSYSTEM\s*:\s*)",
        "credential_request": r"(?i)(?:reveal|print|send|exfiltrate)\b.{0,80}\b(?:password|api[_ -]?key|secret|token)\b",
    }
    flags = [name for name, pattern in patterns.items() if re.search(pattern, value)]
    return {"flags": flags, "review_required": bool(flags), "detector": "heuristic", "safe_content_certified": False, "content_is_instruction": False}


def url_policy(p: dict) -> dict:
    value = text(p.get("url"), "url")
    hosts = p.get("allowed_hosts")
    if not isinstance(hosts, list) or not hosts or any(not isinstance(x, str) or not x for x in hosts):
        raise ValueError("allowed_hosts_required")
    reasons = []
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode().lower().rstrip(".")
        port = parsed.port
        allowed = {x.encode("idna").decode().lower().rstrip(".") for x in hosts}
    except (ValueError, UnicodeError) as exc:
        raise ValueError("malformed_url") from exc
    if parsed.scheme != "https":
        reasons.append("https_required")
    if parsed.username is not None or parsed.password is not None:
        reasons.append("url_credentials_denied")
    if parsed.fragment or port not in {None, 443}:
        reasons.append("fragment_or_port_denied")
    if host not in allowed:
        reasons.append("host_not_allowlisted")
    if "\\" in value or any(ord(c) < 33 for c in value):
        reasons.append("ambiguous_url")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        reasons.append("local_host_denied")
    try:
        if not ipaddress.ip_address(host).is_global:
            reasons.append("nonpublic_ip_denied")
    except ValueError:
        # Numeric forms must not bypass literal IP checks (e.g. 2130706433 or 127.1).
        if re.fullmatch(r"[0-9.]+", host) or host.lower().startswith("0x"):
            reasons.append("ambiguous_numeric_host")
    return {"candidate_allowed": not reasons, "reasons": reasons, "dns_checked": False, "redirects_checked": False, "network_request_performed": False}


def path_policy(p: dict) -> dict:
    value = text(p.get("path"), "path")
    decoded = value
    for _ in range(3):
        updated = unquote(decoded)
        if updated == decoded:
            break
        decoded = updated
    normalized = decoded.replace("\\", "/")
    posix, windows = PurePosixPath(normalized), PureWindowsPath(decoded)
    reasons = []
    if posix.is_absolute() or windows.drive or windows.root:
        reasons.append("relative_path_required")
    if ".." in posix.parts:
        reasons.append("parent_traversal_denied")
    if any(ord(c) < 32 for c in decoded) or ":" in decoded or "%" in decoded:
        reasons.append("ambiguous_path")
    if any(part.rstrip(" .").split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))} for part in posix.parts):
        reasons.append("reserved_device_path")
    return {"candidate_allowed": not reasons, "reasons": reasons, "normalized_relative_path": str(posix) if not reasons else None, "symlinks_checked": False, "filesystem_access_performed": False}


def permission_diff(p: dict) -> dict:
    before, after = p.get("before"), p.get("after")
    if any(not isinstance(x, list) or any(not isinstance(v, str) or not v for v in x) for x in (before, after)):
        raise ValueError("permission_lists_required")
    old, new = set(before), set(after)
    added, removed = sorted(new - old), sorted(old - new)
    return {"added": added, "removed": removed, "expansion_detected": bool(added), "review_required": bool(added), "permissions_changed": False}


def tool_contract(p: dict) -> dict:
    definition, request = p.get("definition"), p.get("request")
    if not isinstance(definition, dict) or not isinstance(request, dict):
        raise ValueError("definition_and_request_required")
    operation = text(definition.get("operation"), "operation")
    required = definition.get("required_arguments", [])
    allowed = definition.get("allowed_arguments", required)
    if any(not isinstance(x, list) or any(not isinstance(y, str) for y in x) for x in (required, allowed)):
        raise ValueError("argument_name_lists_required")
    if not set(required) <= set(allowed):
        raise ValueError("required_arguments_not_allowed")
    if not isinstance(definition.get("side_effects"), bool):
        raise ValueError("side_effects_must_be_boolean")
    args = request.get("arguments")
    if not isinstance(args, dict):
        raise ValueError("request_arguments_required")
    reasons = []
    if request.get("operation") != operation:
        reasons.append("operation_mismatch")
    if set(required) - args.keys():
        reasons.append("missing_arguments")
    if args.keys() - set(allowed):
        reasons.append("unknown_arguments")
    return {"contract_valid": not reasons, "reasons": reasons, "gateway_review_required": definition["side_effects"], "authorization_granted": False, "tool_executed": False}


def audit_chain(p: dict) -> dict:
    events = rows(p, "events", allow_empty=True)
    previous = text(p.get("anchor", "genesis"), "anchor")
    bad = []
    for i, item in enumerate(events):
        if not isinstance(item.get("event"), dict):
            raise ValueError("audit_event_object_required")
        computed = digest({"previous": previous, "event": item["event"]})
        if item.get("previous") != previous or item.get("sha256") != computed:
            bad.append(i)
        previous = computed
    return {"integrity_matches": not bad, "invalid_indices": bad, "computed_head": previous, "origin_authenticated": False, "anchor_trusted": False}


def config_check(p: dict) -> dict:
    config = p.get("config")
    if not isinstance(config, dict):
        raise ValueError("config_required")
    failures = []
    for field in ("debug", "test_hooks", "public_bind", "authentication_enabled"):
        if not isinstance(config.get(field), bool):
            raise ValueError(f"{field}_must_be_boolean")
    if config["debug"]:
        failures.append("debug_enabled")
    if config["test_hooks"]:
        failures.append("test_hooks_enabled")
    if config["public_bind"] and not config["authentication_enabled"]:
        failures.append("public_bind_requires_authentication")
    timeout = number_config(config, "timeout_seconds")
    if not 0 < timeout <= 300:
        failures.append("timeout_out_of_bounds")
    return {"passed": not failures, "failures": failures, "configuration_changed": False, "production_security_certified": False}


def number_config(config, field):
    from .common import number
    return number(config.get(field), field)


def dependency_lock(p: dict) -> dict:
    dependencies = rows(p, "dependencies")
    unique_ids(dependencies, "name")
    invalid = []
    for item in dependencies:
        version = text(item.get("version"), "version")
        sha = text(item.get("sha256"), "sha256")
        if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9.-]+)?", version) or not re.fullmatch(r"[a-f0-9]{64}", sha):
            invalid.append(item["name"])
    return {"fully_pinned": not invalid, "invalid_dependencies": invalid, "lock_sha256": digest(dependencies), "vulnerabilities_checked": False, "packages_installed": False}


def backup_verify(p: dict) -> dict:
    backup = p.get("backup")
    if not isinstance(backup, dict):
        raise ValueError("backup_required")
    expected_schema = text(p.get("expected_schema"), "expected_schema")
    checksum = text(p.get("sha256"), "sha256")
    computed = digest(backup)
    matches = checksum == computed
    compatible = backup.get("schema_version") == expected_schema
    return {"integrity_matches": matches, "schema_compatible": compatible, "eligible_for_restore_review": matches and compatible, "computed_sha256": computed, "origin_authenticated": False, "restore_performed": False}


def provenance_trace(p: dict) -> dict:
    sources = rows(p, "sources")
    tasks = [{"id": x.get("id"), "dependencies": x.get("parents", [])} for x in sources]
    index, order, _ = graph({"tasks": tasks})
    target = text(p.get("target"), "target")
    if target not in index:
        raise ValueError("unknown_provenance_target")
    lineage = {target}
    for identifier in reversed(order):
        if identifier in lineage:
            lineage.update(index[identifier].get("dependencies", []))
    result = [x for x in order if x in lineage]
    return {"lineage_ids": result, "root_ids": [x for x in result if not index[x].get("dependencies")], "lineage_complete_for_supplied_graph": True, "source_truth_verified": False}


CAPABILITIES = (
    (81, "injection_scan", injection_scan), (82, "url_policy", url_policy),
    (83, "path_policy", path_policy), (84, "permission_diff", permission_diff),
    (85, "tool_contract", tool_contract), (86, "audit_chain", audit_chain),
    (87, "config_check", config_check), (88, "dependency_lock", dependency_lock),
    (89, "backup_verify", backup_verify), (90, "provenance_trace", provenance_trace),
)

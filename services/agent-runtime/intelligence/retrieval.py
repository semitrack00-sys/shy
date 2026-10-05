from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from .common import canonical, digest, integer, number, rows, text, timestamp, tokens, unique_ids


def chunk_text(p: dict) -> dict:
    source = text(p.get("source_id"), "source_id")
    value = text(p.get("text"))
    size = integer(p.get("chunk_chars", 1000), "chunk_chars", 32, 8000)
    overlap = integer(p.get("overlap", 100), "overlap", 0, size - 1)
    chunks = []
    start = 0
    while start < len(value):
        end = min(start + size, len(value))
        chunks.append({"id": f"{source}:{start}:{end}", "source_id": source, "start": start, "end": end, "text": value[start:end]})
        if end == len(value):
            break
        start = end - overlap
        if len(chunks) >= 500:
            raise ValueError("chunk_limit_exceeded")
    return {"chunks": chunks, "content_sha256": digest(value)}


def scoped_passages(p: dict) -> list[dict]:
    scope = text(p.get("scope"), "scope")
    passages = rows(p, "passages", allow_empty=True)
    unique_ids(passages)
    for item in passages:
        text(item.get("scope"), "passage_scope")
        text(item.get("text"), "passage_text")
        text(item.get("source_id"), "source_id")
    return [item for item in passages if item["scope"] == scope]


def rank_passages(p: dict) -> dict:
    query = set(tokens(text(p.get("query"), "query")))
    if not query:
        raise ValueError("query_tokens_required")
    passages = scoped_passages(p)
    counts = [Counter(tokens(item["text"])) for item in passages]
    average = sum(sum(x.values()) for x in counts) / max(len(counts), 1)
    df = Counter(word for count in counts for word in count)
    results = []
    for passage, count in zip(passages, counts):
        score = 0.0
        length = sum(count.values())
        for term in query:
            frequency = count[term]
            if frequency:
                idf = math.log(1 + (len(counts) - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / max(average, 1)))
        if score:
            results.append({**passage, "score": round(score, 8)})
    results.sort(key=lambda x: (-x["score"], x["id"]))
    limit = integer(p.get("limit", 8), "limit", 1, 100)
    return {"passages": results[:limit], "eligible_count": len(passages), "method": "BM25", "scope_authenticated": False}


def fuse_rankings(p: dict) -> dict:
    rankings = p.get("rankings")
    if not isinstance(rankings, list) or not rankings or any(not isinstance(x, list) for x in rankings):
        raise ValueError("rankings_required")
    k = integer(p.get("k", 60), "k", 1, 1000)
    scores = defaultdict(float)
    for ranking in rankings:
        if any(not isinstance(x, str) or not x for x in ranking) or len(set(ranking)) != len(ranking):
            raise ValueError("ranking_ids_must_be_unique_strings")
        for rank, item in enumerate(ranking, 1):
            scores[item] += 1 / (k + rank)
    return {"ranking": [{"id": item, "score": score} for item, score in sorted(scores.items(), key=lambda x: (-x[1], x[0]))]}


def pack_context(p: dict) -> dict:
    budget = integer(p.get("max_chars", 4000), "max_chars", 1, 16000)
    passages = scoped_passages(p)
    selected = []
    used = 0
    for item in passages:
        # Citation labels count toward the budget; partial evidence is never silently emitted.
        block = f"[{item['id']}] {item['text']}\n"
        if used + len(block) <= budget:
            selected.append({"id": item["id"], "source_id": item["source_id"], "block": block})
            used += len(block)
    return {"context": "".join(x["block"] for x in selected), "citation_ids": [x["id"] for x in selected], "chars": used, "omitted_count": len(passages) - len(selected)}


def validate_citations(p: dict) -> dict:
    passages = scoped_passages(p)
    index = {x["id"]: x["text"] for x in passages}
    citations = rows(p, "citations", allow_empty=True)
    checks = []
    for citation in citations:
        identifier = text(citation.get("id"), "citation_id")
        quote = text(citation.get("quote"), "quote")
        present = identifier in index
        checks.append({"id": identifier, "valid": present and quote in index[identifier], "reason": "ok" if present and quote in index[identifier] else "quote_not_found" if present else "unknown_or_out_of_scope_source"})
    return {"citations": checks, "all_valid": bool(checks) and all(x["valid"] for x in checks), "semantic_support_verified": False}


def detect_conflicts(p: dict) -> dict:
    claims = rows(p, "claims")
    groups = defaultdict(list)
    for item in claims:
        key = (text(item.get("subject"), "subject"), text(item.get("predicate"), "predicate"))
        text(item.get("source_id"), "source_id")
        if "value" not in item:
            raise ValueError("claim_value_required")
        groups[key].append(item)
    conflicts = []
    for (subject, predicate), items in groups.items():
        if len({canonical(x["value"]) for x in items}) > 1:
            conflicts.append({"subject": subject, "predicate": predicate, "source_ids": sorted({x["source_id"] for x in items}), "values": [x["value"] for x in items]})
    return {"conflicts": conflicts, "conflict_free": not conflicts, "method": "structured_claim_equality"}


def freshness(p: dict) -> dict:
    now = timestamp(p.get("now"), "now")
    ttl = number(p.get("ttl_seconds"), "ttl_seconds", 0)
    result = []
    for item in rows(p, "sources"):
        identifier = text(item.get("id"), "id")
        age = (now - timestamp(item.get("observed_at"), "observed_at")).total_seconds()
        result.append({"id": identifier, "age_seconds": age, "fresh": 0 <= age <= ttl, "future_timestamp": age < 0})
    return {"sources": result, "all_fresh": all(x["fresh"] for x in result)}


def consolidate_memory(p: dict) -> dict:
    scope = text(p.get("scope"), "scope")
    groups = defaultdict(list)
    for item in rows(p, "records", allow_empty=True):
        text(item.get("scope"), "record_scope")
        if item["scope"] != scope:
            continue
        if item.get("verified") is not True:
            continue
        identifier = text(item.get("id"), "id")
        key = text(item.get("subject"), "subject")
        if "value" not in item:
            raise ValueError("memory_value_required")
        groups[key].append({**item, "id": identifier, "at": timestamp(item.get("observed_at"))})
    active, superseded, conflicts = [], [], []
    for subject, items in sorted(groups.items()):
        items.sort(key=lambda x: (x["at"], x["id"]), reverse=True)
        newest = [x for x in items if x["at"] == items[0]["at"]]
        if len({canonical(x["value"]) for x in newest}) > 1:
            conflicts.append(subject)
            continue
        active.append({k: v for k, v in items[0].items() if k != "at"})
        superseded.extend(x["id"] for x in items[1:])
    return {"active_records": active, "superseded_ids": superseded, "conflicting_subjects": conflicts, "persistent_change_applied": False}


_REDACTIONS = (
    ("credential", re.compile(r"(?i)\b(?:api[_ -]?key|password|secret|token)\s*[:=]\s*[\"']?[^\s,;\"']+")),
    ("bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
)


def redact_text(p: dict) -> dict:
    value = text(p.get("text"))
    counts = {}
    for label, pattern in _REDACTIONS:
        value, count = pattern.subn(f"[REDACTED:{label}]", value)
        if count:
            counts[label] = count
    return {"text": value, "redaction_counts": counts, "exhaustive_detection": False}


def answerability(p: dict) -> dict:
    ranked = rank_passages(p)
    query = set(tokens(p["query"]))
    found = set(word for item in ranked["passages"] for word in tokens(item["text"]))
    coverage = len(query & found) / len(query)
    threshold = number(p.get("min_coverage", 0.5), "min_coverage", 0)
    if threshold > 1:
        raise ValueError("min_coverage_above_one")
    conflicts = detect_conflicts({"claims": p["claims"]})["conflicts"] if p.get("claims") else []
    sufficient = bool(ranked["passages"]) and coverage >= threshold and not conflicts
    return {"answerable": sufficient, "lexical_coverage": coverage, "missing_terms": sorted(query - found), "conflicts": conflicts, "reason": "lexical_evidence_available" if sufficient else "insufficient_or_conflicting_evidence", "factual_truth_verified": False}


CAPABILITIES = (
    (51, "chunk_text", chunk_text), (52, "rank_passages", rank_passages),
    (53, "fuse_rankings", fuse_rankings), (54, "pack_context", pack_context),
    (55, "validate_citations", validate_citations), (56, "detect_conflicts", detect_conflicts),
    (57, "source_freshness", freshness), (58, "consolidate_memory", consolidate_memory),
    (59, "redact_text", redact_text), (60, "answerability", answerability),
)

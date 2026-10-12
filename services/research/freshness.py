"""Bounded provider date estimates; retrieval time is never publication proof."""
import re
import unicodedata
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

from .citation_validator import validate_citation_references


def utc_now():
    return datetime.now(timezone.utc)


# Fixed phrase matching, not language detection, translation or intent analysis.
_HINTS = (
    (0, 'english_hint', r"\b(?:today|right now)\b"),
    (7, 'english_hint', r"\b(?:latest|current|recent|this week|up to date)\b"),
    (0, 'french_hint', r"\b(?:aujourd'hui|en ce moment)\b"),
    (7, 'french_hint', r"\b(?:cette semaine|récent(?:e|s|es)?|dernières nouvelles|à jour)\b"),
    (0, 'haitian_creole_hint', r"\b(?:jodi a|jodia|kounye a)\b"),
    (7, 'haitian_creole_hint', r"\b(?:semèn sa a|dènye nouvèl|dènye enfòmasyon)\b"),
)
_PATTERNS = tuple((days, basis, re.compile(pattern)) for days, basis, pattern in _HINTS)


def window_selection(message, freshness="auto"):
    """Choose the shortest matched UTC window; never infer unstated dates."""
    if freshness != 'auto':
        windows = {'same_day': 0, 'past_week': 7, 'past_month': 30, 'any_date': None}
        if freshness not in windows:
            raise ValueError('Invalid research freshness selection')
        return windows[freshness], 'user_selected'
    text = ' '.join(unicodedata.normalize('NFKC', message).casefold().replace('’', "'").split())
    matches = [(days, basis) for days, basis, pattern in _PATTERNS if pattern.search(text)]
    if not matches:
        return None, 'no_window'
    days = min(item[0] for item in matches)
    bases = {basis for candidate, basis in matches if candidate == days}
    return days, next(iter(bases)) if len(bases) == 1 else 'mixed_hint'


def requested_window(message, freshness="auto"):
    """Compatibility helper for source cards and citation gates."""
    return window_selection(message, freshness)[0]


def source_timing(raw, now, max_age_days=30):
    result = {'date_basis': 'provider_publication_or_update_estimate', 'source_date_status': 'unknown'}
    if raw is None or raw == '':
        return result
    if not isinstance(raw, str) or len(raw) > 120:
        return {**result, 'source_date_status': 'invalid'}
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            value = date.fromisoformat(raw)
            future = value > now.date()
        else:
            if re.match(r'^\d{4}-\d{2}-\d{2}T', raw):
                stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            elif re.fullmatch(r'(?:[A-Za-z]{3}, )?\d{1,2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} (?:GMT|[+-]\d{4})', raw):
                stamp = parsedate_to_datetime(raw)
            else:
                raise ValueError('Unsupported date format')
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError('Timestamp needs a timezone')
            stamp = stamp.astimezone(timezone.utc)
            value = stamp.date()
            future = stamp > now
        age = (now.date() - value).days
        return {**result, 'source_date': raw, 'source_age_days': age,
                'source_date_status': 'future' if future else ('recent' if age <= max_age_days else 'stale')}
    except (ValueError, TypeError, OverflowError):
        return {**result, 'source_date_status': 'invalid'}


def evidence_timing(payload, sources, now, window):
    rows = payload.get('evidence') or payload.get('results') or []
    # Duplicate URLs without a source table must not allow one fresh row to
    # silently authorize a different stale row at the same URL.
    indexed = {}
    for row in rows:
        indexed.setdefault(str(row.get('url', '')).strip(), []).append(row)
    reports = []
    for source in sources:
        matches = indexed[source['url']]
        timings = [source_timing(row.get('source_date'), now, 30 if window is None else window) for row in matches]
        timing = next((item for item in timings if item['source_date_status'] != 'recent'), timings[0])
        reports.append({'number': source['number'], **timing})
    return reports


def validate_current_citations(text, sources, reports, window):
    if window is None:
        return
    eligible = {item['number'] for item in reports if item['source_date_status'] == 'recent'}
    references = validate_citation_references(text, sources).valid_references
    if not references or not set(references) <= eligible:
        raise ValueError('Current answer cites unavailable, stale or undated evidence')

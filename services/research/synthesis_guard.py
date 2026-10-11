"""Citation membership checks, not independent verification of source claims."""
import ipaddress
import re
from urllib.parse import urlsplit
from .citation_validator import validate_citation_references


def public_source_url(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 2048 or re.search(r'[\s\x00-\x1f\\]', value):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname
        if url.scheme not in ('https', 'http') or not host or url.username or url.password:
            return False
        if url.port not in (None, 80, 443) or host.lower() in ('localhost', 'localhost.localdomain') or host.lower().endswith(('.local', '.localhost', '.internal')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            labels = host.rstrip('.').split('.')
            return len(labels) >= 2 and len(host) <= 253 and bool(re.search(r'[a-zA-Z]', labels[-1])) and all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label) for label in labels)
    except ValueError:
        return False


def synthesis_sources(payload: dict) -> list[dict]:
    evidence = payload.get('evidence') or payload.get('results') or []
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 12:
        raise ValueError('Bounded research evidence is required.')
    sources = []
    for index, item in enumerate(evidence, start=1):
        if not isinstance(item, dict): raise ValueError('Malformed research evidence.')
        url = str(item.get('url', '')).strip()
        if not public_source_url(url): raise ValueError('Research source must have a public HTTP URL.')
        sources.append({'number': index, 'url': url})
    supplied = payload.get('sources')
    if supplied is not None:
        if not isinstance(supplied, list) or len(supplied) != len(sources):
            raise ValueError('Source table must match the evidence inventory.')
        numbers = set(); urls = set(); bound = []
        for source in supplied:
            if not isinstance(source, dict): raise ValueError('Malformed source table.')
            number = source.get('number'); url = str(source.get('url', '')).strip()
            if type(number) is not int or number in numbers or url in urls or not public_source_url(url):
                raise ValueError('Invalid source numbering or URL.')
            numbers.add(number); urls.add(url); bound.append({'number':number, 'url':url})
        if numbers != set(range(1, len(sources)+1)) or urls != {source['url'] for source in sources}:
            raise ValueError('Source table and evidence inventory disagree.')
        return sorted(bound, key=lambda source: source['number'])
    return sources


def validate_synthesis(text: str, sources: list[dict]) -> None:
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError('Bounded research answer is required.')
    if text.count('[') > 100:
        raise ValueError('Too many citation tokens.')
    report = validate_citation_references(text, sources)
    if not report.is_valid or not report.valid_references:
        raise ValueError('Research answer must cite available evidence using numeric references.')
    allowed = {source['url'] for source in sources}
    for url in re.findall(r'https?://[^\s<>\[\]"\']+', text):
        if url.rstrip(').,;!?') not in allowed:
            raise ValueError('Research answer introduces a URL outside its evidence set.')

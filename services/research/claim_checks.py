"""Conservative supplied-field comparisons, never semantic truth verification."""
import re
import unicodedata
from datetime import date
from decimal import Decimal


class ResearchAnswer(str):
    def __new__(cls, text, mode, model_invoked):
        answer = super().__new__(cls, text)
        answer.mode = mode
        answer.model_invoked = model_invoked
        return answer

    def public_metadata(self):
        return {'mode': self.mode, 'model_invoked': self.model_invoked,
                'semantic_truth_verified': False}


def _atomic_field(snippet):
    if not isinstance(snippet, str) or not 1 <= len(snippet) <= 800:
        return None
    text = unicodedata.normalize('NFKC', snippet).strip()
    match = re.fullmatch(r'([A-Za-z][A-Za-z0-9 .()/_-]{1,79}):\s*(.{1,120})', text)
    if not match:
        return None
    label, value = match.groups()
    key = ' '.join(label.casefold().split())
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        try:
            date.fromisoformat(value)
        except ValueError:
            return None
        return key, label, value, ('date', value)
    quantity = re.fullmatch(r'([+-]?\d{1,12}(?:\.\d{1,8})?)\s*(%|USD|EUR|HTG|km|mi|kg|lb|days|hours)?', value, re.I)
    if not quantity:
        return None
    amount, unit = quantity.groups()
    return key, label, value, ((unit or 'unitless').casefold(), Decimal(amount))


def disagreement_pairs(payload, sources, eligible_numbers=None):
    """Return bounded possible disagreements bound to checked source numbers."""
    rows = payload.get('evidence') or payload.get('results') or []
    number_by_url = {source['url']: source['number'] for source in sources}
    id_numbers = {}
    fields = []
    for row in rows:
        number = number_by_url[str(row.get('url', '')).strip()]
        identifier = row.get('evidence_id')
        if isinstance(identifier, str):
            if identifier in id_numbers:
                raise ValueError('Duplicate evidence identifiers')
            id_numbers[identifier] = number
        if eligible_numbers is not None and number not in eligible_numbers:
            continue
        field = _atomic_field(row.get('snippet'))
        if field:
            fields.append((number, field))
    reports = []
    seen = set()
    for index, (left_number, left) in enumerate(fields):
        for right_number, right in fields[index+1:]:
            # Equal labels alone do not establish a shared subject or date.
            # Differing units are incomparable; no implicit conversion occurs.
            if left_number != right_number and left[0] == right[0] and left[3][0] == right[3][0] and left[3][1] != right[3][1]:
                pair = tuple(sorted((left_number, right_number)))
                if pair not in seen:
                    seen.add(pair)
                    reports.append({'left': left_number, 'right': right_number, 'label': left[1],
                                    'left_value': left[2], 'right_value': right[2], 'basis': 'matching_field_different_value'})
    conflicts = payload.get('conflicts')
    if conflicts is None:
        conflicts = []
    if not isinstance(conflicts, list) or len(conflicts) > 66:
        raise ValueError('Malformed or excessive conflict records')
    for conflict in conflicts:
        if not isinstance(conflict, dict) or conflict.get('relation') != 'CONTRADICTS':
            raise ValueError('Invalid conflict record')
        if not isinstance(conflict.get('left_evidence_id'), str) or not isinstance(conflict.get('right_evidence_id'), str):
            raise ValueError('Invalid conflict identifiers')
        left = id_numbers.get(conflict.get('left_evidence_id'))
        right = id_numbers.get(conflict.get('right_evidence_id'))
        if left is None or right is None or left == right:
            raise ValueError('Conflict references unavailable evidence')
        if eligible_numbers is not None and not {left, right} <= eligible_numbers:
            continue
        pair = tuple(sorted((left, right)))
        if pair not in seen:
            seen.add(pair)
            reports.append({'left': left, 'right': right, 'basis': 'workflow_conflict_flag'})
    return reports[:4]


def disagreement_clarification(reports):
    lines = ['I found possible disagreements in the supplied evidence. I cannot choose one value from these snippets.']
    for report in reports:
        if report['basis'] == 'matching_field_different_value':
            lines.append(f"- {report['label']}: {report['left_value']} [{report['left']}] versus {report['right_value']} [{report['right']}].")
        else:
            lines.append(f"- The research workflow flagged a possible disagreement between [{report['left']}] and [{report['right']}].")
    lines.append('These may concern different subjects or dates. Which subject and date should I use, or can you provide evidence that resolves the difference?')
    return '\n\n'.join(lines)

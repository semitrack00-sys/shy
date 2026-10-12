"""Explicit bounded public-web requests; no task or local-only overrides."""
from typing import Literal
from pydantic import BaseModel, ConfigDict


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    freshness: Literal['auto', 'same_day', 'past_week', 'past_month', 'any_date']


def validate_research_action(value):
    if not isinstance(value, dict) or value.get('research_request') is None:
        return value
    if value.get('document_question') is not None or value.get('option_comparison') is not None or any(value.get(key) for key in ('task_id', 'cancel_task', 'approval_token')) or value.get('pending_step_id') is not None:
        raise ValueError('research_request_cannot_mix_with_other_actions')
    if value.get('local_only'):
        raise ValueError('public_research_cannot_be_local_only')
    message = value.get('message')
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 1000:
        raise ValueError('explicit_research_query_requires_1_to_1000_characters')
    return {**value, 'message': message.strip()}

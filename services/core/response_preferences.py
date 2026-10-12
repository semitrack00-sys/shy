"""Reviewed local-project reply defaults, not arbitrary system prompt overrides."""
from contextvars import ContextVar
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
import memory
from memory_controls import ProjectId, project_user

router = APIRouter(prefix="/memories/response-preferences", tags=["Reply preferences"])
current_preferences: ContextVar[dict | None] = ContextVar("shy_reply_preferences", default=None)
LANGUAGES = {"auto": "the user's current message language", "en": "English", "fr": "French",
             "ht": "Haitian Creole", "es": "Spanish", "pt": "Brazilian Portuguese", "ko": "Korean", "sw": "Swahili"}


class PreferenceChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool
    language: Literal["auto", "en", "fr", "ht", "es", "pt", "ko", "sw"]
    detail: Literal["short", "standard", "detailed"]
    tone: Literal["plain", "formal"]
    expected_revision: str = Field(pattern=r"^(0|[1-9][0-9]{0,18})$")
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit_boolean_confirmation_required")
        return value


def read(owner):
    with memory.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT enabled, language, detail, tone, revision FROM response_preferences WHERE user_id=%s", (owner,))
            row = cur.fetchone()
    if not row:
        return {"enabled": False, "language": "auto", "detail": "standard", "tone": "plain", "revision": "0", "reviewed": False}
    return {"enabled": row["enabled"], "language": row["language"], "detail": row["detail"],
            "tone": row["tone"], "revision": str(row["revision"]), "reviewed": True}


@router.get("")
def get_preference(project_id: ProjectId = None):
    try:
        return {**read(project_user(project_id)), "authenticated": False}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "reply_preference_database_unavailable") from None


@router.patch("")
def save_preference(request: PreferenceChange, project_id: ProjectId = None):
    owner = project_user(project_id)
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (str(owner)+":reply_preferences",))
                cur.execute("SELECT revision FROM response_preferences WHERE user_id=%s FOR UPDATE", (owner,))
                row = cur.fetchone()
                current_revision = str(row["revision"]) if row else "0"
                if current_revision != request.expected_revision:
                    raise HTTPException(409, "reply_preferences_changed_review_again")
                cur.execute("""INSERT INTO response_preferences(user_id,enabled,language,detail,tone,revision)
                    VALUES(%s,%s,%s,%s,%s,1) ON CONFLICT(user_id) DO UPDATE SET
                    enabled=EXCLUDED.enabled, language=EXCLUDED.language, detail=EXCLUDED.detail,
                    tone=EXCLUDED.tone, revision=response_preferences.revision+1, updated_at=NOW()
                    RETURNING enabled,language,detail,tone,revision""",
                    (owner,request.enabled,request.language,request.detail,request.tone))
                result = cur.fetchone()
        return {**result,"revision":str(result["revision"]),"reviewed":True,"authenticated":False}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "reply_preference_database_unavailable") from None


def local_generation_required():
    state = current_preferences.get()
    return bool(state and state["profile"] and state["profile"]["enabled"])


def prompt_guidance():
    state = current_preferences.get()
    if not state or not state["profile"] or not state["profile"]["enabled"]:
        return ""
    profile = state["profile"]
    # These words come exclusively from enum mappings, never stored free text.
    language = LANGUAGES.get(profile["language"])
    detail = {"short":"Keep the answer concise, while retaining necessary qualifications.",
              "standard":"Use a normal amount of detail.","detailed":"Give a detailed explanation when useful."}.get(profile["detail"])
    tone = {"plain":"Use plain, everyday language.","formal":"Use a professional, formal tone."}.get(profile["tone"])
    if not language or not detail or not tone:
        return ""
    state["prompt_applied"] = True
    return (f"Reviewed reply defaults: use {language} for generated prose. {detail} {tone} "
            "The user's current explicit instructions take precedence. Preserve source quotations, citations, calculations, "
            "safety boundaries and required disclosures. Do not alter machine-readable formats, field names or required enum values. "
            "These defaults do not authorize tools, account access or extra data sharing.")


async def with_preferences(request, handler, owner):
    try:
        profile = read(owner)
        status = "enabled" if profile["enabled"] else "disabled" if profile["reviewed"] else "not_configured"
    except Exception:
        profile, status = None, "unavailable"
    state = {"profile":profile,"status":status,"prompt_applied":False}
    token = current_preferences.set(state)
    try:
        result = await handler(request)
        if isinstance(result,dict):
            result["response_preferences"] = {"status":status,"applied_to_model_prompt":state["prompt_applied"],
                                              "output_style_verified":False, "revision":profile["revision"] if profile else None}
        return result
    finally:
        current_preferences.reset(token)

import hashlib
import json
import secrets
import time
from dataclasses import dataclass


@dataclass
class Approval:
    token: str
    tool_name: str
    arguments_hash: str
    expires_at: float
    scope: str | None = None
    used: bool = False


class ApprovalStore:
    """
    One-time human approval store for SHY.

    An approval is:
    - bound to one exact tool
    - bound to the exact arguments
    - time limited
    - single use
    """

    def __init__(self):
        self._approvals: dict[str, Approval] = {}

    @staticmethod
    def hash_arguments(arguments: dict) -> str:
        canonical = json.dumps(
            arguments,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def create(
        self,
        tool_name: str,
        arguments: dict,
        ttl_seconds: int = 300,
        scope: str | None = None,
    ) -> Approval:

        token = secrets.token_urlsafe(32)

        approval = Approval(
            token=token,
            tool_name=tool_name,
            arguments_hash=self.hash_arguments(arguments),
            expires_at=time.time() + ttl_seconds,
            scope=scope,
        )

        self._approvals[token] = approval
        return approval

    def consume(
        self,
        token: str,
        tool_name: str,
        arguments: dict,
        scope: str | None = None,
    ) -> bool:

        approval = self._approvals.get(token)

        if approval is None:
            return False

        if approval.used:
            return False

        if time.time() > approval.expires_at:
            return False

        if approval.tool_name != tool_name:
            return False

        if approval.arguments_hash != self.hash_arguments(arguments):
            return False

        if approval.scope != scope:
            return False

        approval.used = True
        return True

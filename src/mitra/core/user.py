"""User context variables and resolvers.

Defines the ContextVars used to track the currently authenticated user in a multi-user setup,
and resolves their unique user ID based on headers or API keys.
"""

import contextvars
import hashlib
from typing import Optional

# ── ContextVars ───────────────────────────────────────────────────────────────

request_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)

# ── HEADERS mapping: HTTP header name → ContextVar ────────────────────────────
# Checked by registry.py to auto-collect headers on every request.

HEADERS = {
    "x-user-id": request_user_id,
}

# ── Resolvers ─────────────────────────────────────────────────────────────────


async def get_current_user_id() -> str:
    """Resolve the currently authenticated user's ID (expected to be their email address).

    Checks:
    1. The 'x-user-id' ContextVar (set by client header).
    2. The 'USER_ID' environment variable.
    3. The authenticated user's email address from Clockify (if configured).

    Raises:
        ValueError: If no user context/email can be established.
    """
    # 1. Direct ContextVar
    uid = request_user_id.get()
    if uid:
        return uid

    # 2. Environment Variable
    import os
    env_uid = os.environ.get("USER_ID")
    if env_uid:
        return env_uid

    # 3. Fallback: Query Clockify to retrieve the user's email address
    from mitra.integrations.clockify.context import get_clockify_api_key
    clockify_key = get_clockify_api_key()
    if clockify_key:
        try:
            from mitra.integrations.clockify.client import ClockifyClient
            client = ClockifyClient(clockify_key)
            user_info = await client.get_current_user()
            email = user_info.get("email")
            if email:
                return email
        except Exception:
            pass

    raise ValueError(
        "Could not establish user identity email. Please specify the 'x-user-id' header, "
        "set the 'USER_ID' environment variable, or configure Clockify credentials."
    )

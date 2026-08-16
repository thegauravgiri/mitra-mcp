"""ContextVar carrying the authenticated caller's identity for the duration of a request."""
import contextvars
from typing import Optional

CURRENT_USER_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_user_id", default=None
)


def get_current_user_id() -> Optional[str]:
    return CURRENT_USER_ID.get()

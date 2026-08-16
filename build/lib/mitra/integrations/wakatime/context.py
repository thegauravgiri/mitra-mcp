"""WakaTime context variables and credential resolvers."""

import contextvars
from typing import Optional

from mitra.core.context import resolve_credential

# ── ContextVars ───────────────────────────────────────────────────────────────

request_wakatime_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "wakatime_api_key", default=None
)

# ── HEADERS mapping ──────────────────────────────────────────────────────────

HEADERS = {
    "x-wakatime-api-key": request_wakatime_api_key,
}

# ── Resolver functions ────────────────────────────────────────────────────────


def get_wakatime_api_key() -> Optional[str]:
    """Retrieves the WakaTime API key from context or environment variables."""
    return resolve_credential(request_wakatime_api_key, "WAKATIME_API_KEY")

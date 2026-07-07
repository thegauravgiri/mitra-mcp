"""Clockify context variables and credential resolvers.

Defines the ContextVars used for per-request credential injection (SSE mode)
and the HEADERS mapping consumed by the auto-discovery middleware.
"""

import contextvars
from typing import Optional

from mitra.core.context import resolve_credential

# ── ContextVars (set by SSE middleware from HTTP headers) ──────────────────────

request_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "clockify_api_key", default=None
)
request_workspace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "clockify_workspace_id", default=None
)
request_project_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "clockify_project_id", default=None
)

# ── HEADERS mapping: HTTP header name → ContextVar ────────────────────────────
# The middleware auto-collects this from every integration's context module.

HEADERS = {
    "x-clockify-api-key": request_api_key,
    "x-clockify-workspace-id": request_workspace_id,
    "x-clockify-project-id": request_project_id,
}

# ── Resolver functions ────────────────────────────────────────────────────────


def get_clockify_api_key() -> Optional[str]:
    """Retrieves the Clockify API key from context or environment variables."""
    return resolve_credential(request_api_key, "CLOCKIFY_API_KEY")


def get_workspace_id() -> Optional[str]:
    """Retrieves the workspace ID from context or environment variables."""
    return resolve_credential(request_workspace_id, "CLOCKIFY_WORKSPACE_ID")


def get_project_id() -> Optional[str]:
    """Retrieves the default project ID from context or environment variables."""
    return resolve_credential(request_project_id, "CLOCKIFY_PROJECT_ID")

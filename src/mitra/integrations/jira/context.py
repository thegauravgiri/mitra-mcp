"""Jira context variables and credential resolvers."""

import contextvars
from typing import Optional

from mitra.core.context import resolve_credential

# ── ContextVars ───────────────────────────────────────────────────────────────

request_jira_email: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "jira_email", default=None
)
request_jira_api_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "jira_api_token", default=None
)
request_jira_url: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "jira_url", default=None
)

# ── HEADERS mapping ──────────────────────────────────────────────────────────

HEADERS = {
    "x-jira-email": request_jira_email,
    "x-jira-api-token": request_jira_api_token,
    "x-jira-url": request_jira_url,
}

# ── Resolver functions ────────────────────────────────────────────────────────


def get_jira_email() -> Optional[str]:
    """Retrieves the Jira account email from context or environment variables."""
    return resolve_credential(request_jira_email, "JIRA_EMAIL")


def get_jira_api_token() -> Optional[str]:
    """Retrieves the Jira API token from context or environment variables."""
    return resolve_credential(request_jira_api_token, "JIRA_API_TOKEN")


def get_jira_url() -> Optional[str]:
    """Retrieves the Jira site URL from context or environment variables."""
    return resolve_credential(request_jira_url, "JIRA_URL")

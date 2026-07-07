"""Azure DevOps context variables and credential resolvers."""

import contextvars
from typing import Optional

from mitra.core.context import resolve_credential

# ── ContextVars ───────────────────────────────────────────────────────────────

request_azure_devops_pat: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "azure_devops_pat", default=None
)
request_azure_devops_org: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "azure_devops_org", default=None
)

# ── HEADERS mapping ──────────────────────────────────────────────────────────

HEADERS = {
    "x-azure-devops-pat": request_azure_devops_pat,
    "x-azure-devops-org": request_azure_devops_org,
}

# ── Resolver functions ────────────────────────────────────────────────────────


def get_azure_devops_pat() -> Optional[str]:
    """Retrieves the Azure DevOps PAT from context or environment variables."""
    return resolve_credential(request_azure_devops_pat, "AZURE_DEVOPS_PAT")


def get_azure_devops_org() -> Optional[str]:
    """Retrieves the Azure DevOps organization URL from context or environment variables."""
    return resolve_credential(request_azure_devops_org, "AZURE_DEVOPS_ORG")

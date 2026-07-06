import os
import contextvars
from typing import Optional

# ContextVars to handle request-specific configurations in multi-user remote setups (via HTTP/SSE headers)
request_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_api_key", default=None)
request_workspace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_workspace_id", default=None)
request_project_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_project_id", default=None)
request_wakatime_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_wakatime_api_key", default=None)
request_azure_devops_pat: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_azure_devops_pat", default=None)
request_azure_devops_org: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_azure_devops_org", default=None)


def get_clockify_api_key() -> Optional[str]:
    """Retrieves the Clockify API key from context or environment variables."""
    return request_api_key.get() or os.environ.get("CLOCKIFY_API_KEY")


def get_workspace_id() -> Optional[str]:
    """Retrieves the workspace ID from context or environment variables."""
    return request_workspace_id.get() or os.environ.get("CLOCKIFY_WORKSPACE_ID")


def get_project_id() -> Optional[str]:
    """Retrieves the default project ID from context or environment variables."""
    return request_project_id.get() or os.environ.get("CLOCKIFY_PROJECT_ID")


def get_wakatime_api_key() -> Optional[str]:
    """Retrieves the WakaTime API key from context or environment variables."""
    return request_wakatime_api_key.get() or os.environ.get("WAKATIME_API_KEY")


def get_azure_devops_pat() -> Optional[str]:
    """Retrieves the Azure DevOps PAT from context or environment variables."""
    return request_azure_devops_pat.get() or os.environ.get("AZURE_DEVOPS_PAT")


def get_azure_devops_org() -> Optional[str]:
    """Retrieves the Azure DevOps organization URL from context or environment variables."""
    return request_azure_devops_org.get() or os.environ.get("AZURE_DEVOPS_ORG")

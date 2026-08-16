"""Model layer: what each third-party service needs from the vault's add-key form.

This is the single source of truth for service metadata — the web app's
template renders its form fields from it, the controller validates/stores
against it, and cli.py's vault_injection_middleware reads it to know which
ContextVar-backing header each field corresponds to.
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class ExtraField:
    """A non-secret companion input (e.g. an org URL) collected alongside the key."""

    name: str
    label: str
    header: str
    placeholder: str = ""
    required: bool = False


@dataclass(frozen=True)
class ServiceConfig:
    key: str
    label: str
    secret_label: str
    secret_header: str
    extra_fields: List[ExtraField] = field(default_factory=list)


SERVICES: Dict[str, ServiceConfig] = {
    "clockify": ServiceConfig(
        key="clockify",
        label="Clockify",
        secret_label="API key",
        secret_header="x-clockify-api-key",
        extra_fields=[
            ExtraField(
                name="workspace_id",
                label="Workspace ID",
                header="x-clockify-workspace-id",
                placeholder="Optional — needed by some Clockify tools",
                required=False,
            ),
        ],
    ),
    "wakatime": ServiceConfig(
        key="wakatime",
        label="WakaTime",
        secret_label="API key",
        secret_header="x-wakatime-api-key",
    ),
    "azure_devops": ServiceConfig(
        key="azure_devops",
        label="Azure DevOps",
        secret_label="Personal access token",
        secret_header="x-azure-devops-pat",
        extra_fields=[
            ExtraField(
                name="organization_url",
                label="Organization URL",
                header="x-azure-devops-org",
                placeholder="https://dev.azure.com/your-org",
                required=True,
            ),
        ],
    ),
}

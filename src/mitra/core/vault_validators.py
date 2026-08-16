"""One-time provider validation for keys submitted through the web vault UI.

Each validator makes a single minimal read-only request against the provider
using the key just entered, so a bad key is rejected before it's ever stored.
Never log the secret and never surface the provider's raw response body back
to the caller (it may echo the key in an error message).
"""
import base64
from typing import Any, Dict, Optional

import httpx


class ValidationError(Exception):
    """Raised when a provider rejects a key/PAT, or required metadata is missing."""


async def validate_clockify(secret: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get("https://api.clockify.me/api/v1/user", headers={"X-Api-Key": secret})
    if resp.status_code != 200:
        raise ValidationError("Clockify rejected this API key.")


async def validate_wakatime(secret: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get("https://wakatime.com/api/v1/users/current", auth=(secret, ""))
    if resp.status_code != 200:
        raise ValidationError("WakaTime rejected this API key.")


async def validate_azure_devops(secret: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    org_url = (metadata or {}).get("organization_url")
    if not org_url:
        raise ValidationError("An Azure DevOps organization URL is required.")
    creds = base64.b64encode(f":{secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{org_url.rstrip('/')}/_apis/profile/profiles/me?api-version=7.0",
            headers={"Authorization": f"Basic {creds}"},
        )
    if resp.status_code != 200:
        raise ValidationError("Azure DevOps rejected this PAT or organization URL.")


VALIDATORS = {
    "clockify": validate_clockify,
    "wakatime": validate_wakatime,
    "azure_devops": validate_azure_devops,
}


async def validate_key(service: str, secret: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    validator = VALIDATORS.get(service.lower())
    if validator is None:
        raise ValidationError(f"Unknown service: {service}")
    await validator(secret, metadata)

"""Controller layer: sign-in, key CRUD, and MCP connection info for the vault web app."""
import os
import secrets as secrets_mod
import urllib.parse
from typing import Optional

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from mitra.core import token_auth, vault_validators
from mitra.core.oauth_service import get_credential_service
from mitra.core.vault_service import get_vault_service
from mitra.webapp import session as session_utils
from mitra.webapp.service_config import SERVICES

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()


def _require_session(request: Request) -> Optional[str]:
    cookie = request.cookies.get("mitra_session")
    return session_utils.unsign(cookie) if cookie else None


def _mcp_url(request: Request) -> str:
    return os.environ.get("MCP_RESOURCE_URI") or str(request.base_url).rstrip("/") + "/mcp"


def _notice(request: Request, title: str, message: str, status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "notice.html", {"title": title, "message": message}, status_code=status_code
    )


async def _vault_response(request: Request, user_id: str, error: Optional[str] = None, status_code: int = 200):
    keys = await get_vault_service().list_keys(user_id)
    keys_by_service = {k["service"]: k for k in keys}

    calendar_cred = await get_credential_service().store.get_credential(user_id, "google")

    return templates.TemplateResponse(
        request,
        "vault.html",
        {
            "user_id": user_id,
            "active_tab": "keys",
            "services": list(SERVICES.values()),
            "keys_by_service": keys_by_service,
            "error": error,
            "calendar_connected": calendar_cred is not None,
            "calendar_connected_at": (calendar_cred or {}).get("updated_at"),
            "calendar_connect_url": "/auth/google/start?user_id=" + urllib.parse.quote(user_id),
        },
        status_code=status_code,
    )


@router.get("/vault/login")
async def vault_login(request: Request):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    web_redirect_uri = os.environ.get("GOOGLE_WEB_REDIRECT_URI")
    if not client_id or not web_redirect_uri:
        return _notice(
            request,
            "Configuration error",
            "GOOGLE_CLIENT_ID and GOOGLE_WEB_REDIRECT_URI must be configured on the server.",
            status_code=500,
        )

    state = secrets_mod.token_urlsafe(24)
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={urllib.parse.quote(web_redirect_uri)}&"
        "response_type=code&"
        f"scope={urllib.parse.quote('openid email')}&"
        f"state={state}"
    )
    response = RedirectResponse(auth_url)
    response.set_cookie("mitra_oauth_state", state, httponly=True, max_age=600, samesite="lax")
    return response


@router.get("/vault/callback")
async def vault_callback(request: Request, code: str, state: str):
    cookie_state = request.cookies.get("mitra_oauth_state")
    if not cookie_state or cookie_state != state:
        return _notice(request, "Sign-in failed", "Invalid or expired sign-in state. Please try again.", 400)

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    web_redirect_uri = os.environ.get("GOOGLE_WEB_REDIRECT_URI")

    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": web_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data=payload, timeout=10.0)
    if resp.status_code != 200:
        return _notice(request, "Sign-in failed", "Google rejected the sign-in request. Please try again.", 400)

    data = resp.json()
    id_token = data.get("id_token")
    if not id_token:
        return _notice(request, "Sign-in failed", "Google did not return an ID token.", 400)

    try:
        claims = token_auth.validate_bearer_token(id_token)
    except token_auth.TokenValidationError:
        return _notice(request, "Sign-in failed", "Your Google sign-in could not be verified. Please try again.", 400)

    user_id = claims.get("email") or claims["sub"]
    response = RedirectResponse("/vault", status_code=307)
    response.set_cookie(
        "mitra_session",
        session_utils.sign(user_id),
        httponly=True,
        samesite="lax",
        secure=(request.url.scheme == "https"),
        max_age=60 * 60 * 24 * 30,
    )
    response.delete_cookie("mitra_oauth_state")
    return response


@router.get("/vault/logout")
async def vault_logout():
    response = RedirectResponse("/vault/login")
    response.delete_cookie("mitra_session")
    return response


@router.get("/vault", response_class=HTMLResponse)
async def vault_home(request: Request):
    user_id = _require_session(request)
    if not user_id:
        return RedirectResponse("/vault/login")
    return await _vault_response(request, user_id)


@router.get("/vault/connect", response_class=HTMLResponse)
async def vault_connect(request: Request):
    user_id = _require_session(request)
    if not user_id:
        return RedirectResponse("/vault/login")
    return templates.TemplateResponse(
        request,
        "connect.html",
        {
            "user_id": user_id,
            "active_tab": "connect",
            "mcp_url": _mcp_url(request),
            "metadata_url": str(request.base_url).rstrip("/") + "/.well-known/oauth-protected-resource",
        },
    )


@router.post("/vault/keys")
async def vault_add_key(
    request: Request,
    service: str = Form(...),
    secret: str = Form(...),
    organization_url: str = Form(""),
    workspace_id: str = Form(""),
):
    user_id = _require_session(request)
    if not user_id:
        return RedirectResponse("/vault/login")

    cfg = SERVICES.get(service)
    if cfg is None:
        return await _vault_response(request, user_id, error=f"Unknown service: {service}", status_code=400)

    metadata = {}
    if organization_url:
        metadata["organization_url"] = organization_url
    if workspace_id:
        metadata["workspace_id"] = workspace_id

    missing_required = [f.label for f in cfg.extra_fields if f.required and not metadata.get(f.name)]
    if missing_required:
        return await _vault_response(
            request, user_id, error=f"{cfg.label} requires: {', '.join(missing_required)}", status_code=400
        )

    try:
        await vault_validators.validate_key(service, secret, metadata)
    except vault_validators.ValidationError as exc:
        return await _vault_response(request, user_id, error=str(exc), status_code=400)

    await get_vault_service().save_key(
        user_id=user_id,
        service=service,
        secret=secret,
        metadata=metadata or None,
        last4=secret[-4:] if len(secret) >= 4 else "****",
    )
    return RedirectResponse("/vault", status_code=303)


@router.post("/vault/keys/{service}/delete")
async def vault_delete_key(request: Request, service: str):
    user_id = _require_session(request)
    if not user_id:
        return RedirectResponse("/vault/login")
    await get_vault_service().delete_key(user_id, service)
    return RedirectResponse("/vault", status_code=303)


@router.post("/vault/calendar/disconnect")
async def vault_disconnect_calendar(request: Request):
    user_id = _require_session(request)
    if not user_id:
        return RedirectResponse("/vault/login")
    await get_credential_service().store.delete_credential(user_id, "google")
    return RedirectResponse("/vault", status_code=303)

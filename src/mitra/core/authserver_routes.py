"""Mitra's own OAuth 2.1 authorization-server endpoints for MCP clients.

MCP clients (VSCode, Claude Desktop, etc.) expect to hit a server that IS the
authorization server: they self-register via Dynamic Client Registration
(RFC 7591), redirect the user to /authorize, and exchange a code for a token
at /token — all against the *resource* server's own domain. Pointing them
straight at Google (which doesn't support DCR) is what forces the "enter
your OAuth client ID" fallback dialog.

This module makes Mitra act as that authorization server while delegating
the actual login decision to Google underneath: /authorize silently bounces
the user through Google's real consent screen and mints Mitra's own
short-lived access token (see token_auth.issue_access_token) once Google
confirms identity. Clients never see Google directly.
"""
import base64
import hashlib
import logging
import os
import secrets
import urllib.parse
from typing import Optional

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from mitra.core import token_auth
from mitra.core.authserver_store import get_authserver_store

logger = logging.getLogger("mitra.core.authserver_routes")

router = APIRouter()

AUTH_CODE_TTL_SECONDS = 120
LOGIN_REQUEST_TTL_SECONDS = 600
ACCESS_TOKEN_TTL_SECONDS = 3600


def _resource_uri(request: Request) -> str:
    return os.environ.get("MCP_RESOURCE_URI") or str(request.base_url).rstrip("/") + "/mcp"


def _google_callback_redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/oauth/callback"


def _error_page(title: str, message: str, status_code: int = 400) -> HTMLResponse:
    return HTMLResponse(f"<h3>{title}</h3><p>{message}</p>", status_code=status_code)


def _verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    if method != "S256":
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(computed, code_challenge)


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata(request: Request):
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "registration_endpoint": f"{base}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["openid", "email"],
    })


@router.post("/register")
async def register_client(request: Request):
    """Dynamic Client Registration (RFC 7591) — every caller is trusted equally.

    Public clients only (no client_secret): the auth code exchange is protected
    by PKCE instead, since MCP clients are typically desktop/CLI apps that
    can't keep a secret confidential.
    """
    body = await request.json()
    redirect_uris = body.get("redirect_uris")
    if not redirect_uris or not isinstance(redirect_uris, list):
        return JSONResponse(
            {"error": "invalid_client_metadata", "error_description": "redirect_uris is required"},
            status_code=400,
        )

    client_id = secrets.token_urlsafe(16)
    store = get_authserver_store()
    await store.register_client(client_id, redirect_uris, body.get("client_name"))

    return JSONResponse({
        "client_id": client_id,
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    })


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    state: Optional[str] = None,
    scope: Optional[str] = None,
):
    if response_type != "code":
        return _error_page("Unsupported response_type", "Only 'code' is supported.")
    if code_challenge_method != "S256":
        return _error_page("Unsupported code_challenge_method", "Only 'S256' PKCE is supported.")

    store = get_authserver_store()
    client = await store.get_client(client_id)
    if not client:
        return _error_page("Unknown client", "This client is not registered.", 400)
    if redirect_uri not in client["redirect_uris"]:
        return _error_page("Invalid redirect_uri", "redirect_uri does not match the registered client.", 400)

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not google_client_id:
        return _error_page("Configuration error", "GOOGLE_CLIENT_ID is not configured on the server.", 500)

    login_id = secrets.token_urlsafe(24)
    await store.save_login_request(
        login_id=login_id,
        client_id=client_id,
        redirect_uri=redirect_uri,
        client_state=state,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        ttl_seconds=LOGIN_REQUEST_TTL_SECONDS,
    )

    google_redirect_uri = _google_callback_redirect_uri(request)
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={google_client_id}&"
        f"redirect_uri={urllib.parse.quote(google_redirect_uri)}&"
        "response_type=code&"
        f"scope={urllib.parse.quote('openid email')}&"
        f"state={login_id}"
    )
    return RedirectResponse(auth_url)


@router.get("/oauth/callback")
async def google_callback(request: Request, code: str, state: str):
    """Google redirects here after the user picks an account. `state` is our login_id."""
    store = get_authserver_store()
    login_request = await store.pop_login_request(state)
    if not login_request:
        return _error_page("Sign-in expired", "This sign-in link has expired. Please try connecting again.", 400)

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    google_redirect_uri = _google_callback_redirect_uri(request)

    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": google_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data=payload, timeout=10.0)
    if resp.status_code != 200:
        logger.warning("Google token exchange failed: %s", resp.text)
        return _error_page("Sign-in failed", "Google rejected the sign-in request. Please try again.", 400)

    id_token = resp.json().get("id_token")
    if not id_token:
        return _error_page("Sign-in failed", "Google did not return an ID token.", 400)

    try:
        claims = token_auth.validate_bearer_token(id_token)
    except token_auth.TokenValidationError:
        return _error_page("Sign-in failed", "Your Google sign-in could not be verified. Please try again.", 400)

    user_id = claims.get("email") or claims["sub"]

    auth_code = secrets.token_urlsafe(32)
    await store.save_auth_code(
        code=auth_code,
        client_id=login_request["client_id"],
        redirect_uri=login_request["redirect_uri"],
        code_challenge=login_request["code_challenge"],
        code_challenge_method=login_request["code_challenge_method"],
        user_id=user_id,
        ttl_seconds=AUTH_CODE_TTL_SECONDS,
    )

    params = {"code": auth_code}
    if login_request.get("client_state"):
        params["state"] = login_request["client_state"]
    redirect_to = f"{login_request['redirect_uri']}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(redirect_to)


@router.post("/token")
async def token_endpoint(
    request: Request,
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
):
    store = get_authserver_store()
    resource_uri = _resource_uri(request)

    if grant_type == "authorization_code":
        if not (code and redirect_uri and client_id and code_verifier):
            return JSONResponse(
                {"error": "invalid_request", "error_description": "missing required parameters"},
                status_code=400,
            )

        row = await store.consume_auth_code(code)
        if not row:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "code is invalid, expired, or already used"},
                status_code=400,
            )
        if row["client_id"] != client_id or row["redirect_uri"] != redirect_uri:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "client_id/redirect_uri mismatch"},
                status_code=400,
            )
        if not _verify_pkce(code_verifier, row["code_challenge"], row["code_challenge_method"]):
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                status_code=400,
            )

        user_id = row["user_id"]
        access_token = token_auth.issue_access_token(user_id, resource_uri, ACCESS_TOKEN_TTL_SECONDS)
        new_refresh_token = secrets.token_urlsafe(32)
        await store.save_refresh_token(new_refresh_token, client_id, user_id)

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "refresh_token": new_refresh_token,
            "scope": "openid email",
        })

    if grant_type == "refresh_token":
        if not (refresh_token and client_id):
            return JSONResponse(
                {"error": "invalid_request", "error_description": "missing required parameters"},
                status_code=400,
            )

        row = await store.get_refresh_token(refresh_token)
        if not row or row["client_id"] != client_id:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "refresh_token is invalid or revoked"},
                status_code=400,
            )

        await store.revoke_refresh_token(refresh_token)
        user_id = row["user_id"]
        access_token = token_auth.issue_access_token(user_id, resource_uri, ACCESS_TOKEN_TTL_SECONDS)
        new_refresh_token = secrets.token_urlsafe(32)
        await store.save_refresh_token(new_refresh_token, client_id, user_id)

        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "refresh_token": new_refresh_token,
            "scope": "openid email",
        })

    return JSONResponse(
        {"error": "unsupported_grant_type", "error_description": f"grant_type '{grant_type}' is not supported"},
        status_code=400,
    )

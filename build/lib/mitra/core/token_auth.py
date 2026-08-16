"""Bearer token validation for the MCP resource-server auth layer.

Two kinds of bearer tokens are accepted:

1. Self-issued access tokens, minted by our own OAuth authorization-server
   proxy (see authserver_routes.py) after a client completes the
   authorize -> Google login -> token exchange. HS256, signed with
   MCP_JWT_SECRET, `iss` == MITRA_ISSUER. This is the normal path for any
   MCP client connecting today.
2. Google-issued OIDC ID tokens, verified against Google's published JWKS.
   Kept for backward compatibility with anything already configured to
   send a Google ID token directly.
"""
import os
import time
import uuid
from typing import Any, Dict, Optional

import jwt
from jwt import PyJWKClient

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
MITRA_ISSUER = "mitra-mcp"

_jwks_client: Optional[PyJWKClient] = None


class TokenValidationError(Exception):
    """Raised when a bearer token fails signature, issuer, audience, or claim checks."""


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)
    return _jwks_client


def _jwt_secret() -> str:
    secret = os.environ.get("MCP_JWT_SECRET")
    if not secret:
        raise TokenValidationError("MCP_JWT_SECRET is not configured on the server")
    return secret


def issue_access_token(user_id: str, resource_uri: str, ttl_seconds: int = 3600) -> str:
    """Mints a self-issued access token binding this resource's audience to user_id."""
    now = int(time.time())
    claims = {
        "iss": MITRA_ISSUER,
        "sub": user_id,
        "email": user_id,
        "aud": resource_uri,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, _jwt_secret(), algorithm="HS256")


def _validate_mitra_token(token: str, resource_uri: Optional[str]) -> Dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            audience=resource_uri if resource_uri else None,
            options={"require": ["exp", "iat", "sub"], "verify_aud": bool(resource_uri)},
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError(str(exc)) from exc
    return claims


def _validate_google_id_token(token: str) -> Dict[str, Any]:
    audience = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not audience:
        raise TokenValidationError("GOOGLE_CLIENT_ID is not configured on the server")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError(str(exc)) from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise TokenValidationError(f"unexpected issuer: {claims.get('iss')!r}")

    return claims


def validate_bearer_token(token: str, resource_uri: Optional[str] = None) -> Dict[str, Any]:
    """Validate a bearer token (self-issued or Google ID token) and return its claims."""
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise TokenValidationError(str(exc)) from exc

    if unverified.get("iss") == MITRA_ISSUER:
        return _validate_mitra_token(token, resource_uri)
    return _validate_google_id_token(token)

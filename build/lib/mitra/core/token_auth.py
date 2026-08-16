"""Bearer token validation for the MCP resource-server auth layer.

Validates Google-issued OIDC ID tokens (not OAuth access tokens, which are
opaque and carry no checkable audience claim) against Google's published
JWKS. This is week 1 of the OAuth migration: proves identity only, does not
yet resolve a vault credential from it.
"""
import os
from typing import Any, Dict, Optional

import jwt
from jwt import PyJWKClient

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

_jwks_client: Optional[PyJWKClient] = None


class TokenValidationError(Exception):
    """Raised when a bearer token fails signature, issuer, audience, or claim checks."""


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)
    return _jwks_client


def validate_bearer_token(token: str) -> Dict[str, Any]:
    """Validate a Google ID token and return its claims, or raise TokenValidationError."""
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

"""HMAC-signed session cookie helpers for the vault web app."""
import hashlib
import hmac
import os
from typing import Optional


def _session_secret() -> str:
    secret = os.environ.get("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET must be set to use the web vault UI")
    return secret


def sign(value: str) -> str:
    mac = hmac.new(_session_secret().encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{mac}"


def unsign(signed: str) -> Optional[str]:
    if "." not in signed:
        return None
    value, _, mac = signed.rpartition(".")
    expected = hmac.new(_session_secret().encode(), value.encode(), hashlib.sha256).hexdigest()
    return value if hmac.compare_digest(mac, expected) else None

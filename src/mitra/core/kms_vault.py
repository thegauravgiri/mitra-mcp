"""Envelope encryption helpers backed by Google Cloud KMS.

Each secret is encrypted locally with a random 256-bit data key (DEK) using
AES-256-GCM. The DEK itself is wrapped by a Cloud KMS root key, so the root
key material never leaves KMS and a Postgres-only leak yields nothing usable
without a separate KMS IAM grant.
"""
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_kms_client = None


def _get_kms_client():
    global _kms_client
    if _kms_client is None:
        from google.cloud import kms

        _kms_client = kms.KeyManagementServiceClient()
    return _kms_client


def _root_key_name() -> str:
    name = os.environ.get("KMS_KEY_RESOURCE_NAME")
    if not name:
        raise ValueError(
            "KMS_KEY_RESOURCE_NAME is required to use the key vault, e.g. "
            "projects/<project>/locations/<location>/keyRings/<ring>/cryptoKeys/<key>"
        )
    return name


def generate_dek() -> bytes:
    """Generate a random 256-bit data encryption key. Caller must not persist this."""
    return AESGCM.generate_key(bit_length=256)


def wrap_dek(dek: bytes) -> bytes:
    """Encrypt a DEK under the KMS root key so it's safe to store in Postgres."""
    client = _get_kms_client()
    response = client.encrypt(request={"name": _root_key_name(), "plaintext": dek})
    return response.ciphertext


def unwrap_dek(wrapped_dek: bytes) -> bytes:
    """Decrypt a wrapped DEK via KMS. Caller must not persist or log the result."""
    client = _get_kms_client()
    response = client.decrypt(request={"name": _root_key_name(), "ciphertext": wrapped_dek})
    return response.plaintext


def encrypt_with_dek(plaintext: str, dek: bytes) -> Tuple[bytes, bytes]:
    """Encrypt plaintext under a DEK. Returns (ciphertext, nonce)."""
    aesgcm = AESGCM(dek)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return ciphertext, nonce


def decrypt_with_dek(ciphertext: bytes, nonce: bytes, dek: bytes) -> str:
    """Decrypt ciphertext under a DEK. Caller must not log or cache the result."""
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()

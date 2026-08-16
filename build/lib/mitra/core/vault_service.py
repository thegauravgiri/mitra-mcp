"""High-level key-vault operations: envelope encryption + Postgres persistence.

This is the only vault entry point the auth middleware and the web app should
call — neither talks to kms_vault or vault_store directly. Every decrypt does
a fresh KMS call; nothing is cached beyond the caller's own stack frame.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

from mitra.core import kms_vault
from mitra.core.vault_store import VaultKeyStore

logger = logging.getLogger("mitra.core.vault_service")

_shared_service: Optional["VaultService"] = None


class VaultService:
    def __init__(self, store: VaultKeyStore):
        self.store = store

    async def save_key(
        self,
        user_id: str,
        service: str,
        secret: str,
        metadata: Optional[Dict[str, Any]] = None,
        last4: Optional[str] = None,
    ) -> None:
        dek = kms_vault.generate_dek()
        wrapped_dek = kms_vault.wrap_dek(dek)
        ciphertext, nonce = kms_vault.encrypt_with_dek(secret, dek)
        stored_metadata = dict(metadata or {})
        if last4:
            stored_metadata["_last4"] = last4
        await self.store.save_key(
            user_id=user_id,
            service=service,
            wrapped_dek=wrapped_dek,
            ciphertext=ciphertext,
            nonce=nonce,
            kms_key_version=os.environ.get("KMS_KEY_RESOURCE_NAME", ""),
            metadata=stored_metadata,
        )

    async def get_key(self, user_id: str, service: str) -> Optional[Dict[str, Any]]:
        row = await self.store.get_key_row(user_id, service)
        if row is None:
            return None
        try:
            dek = kms_vault.unwrap_dek(bytes(row["wrapped_dek"]))
            secret = kms_vault.decrypt_with_dek(bytes(row["ciphertext"]), bytes(row["nonce"]), dek)
        except Exception:
            logger.exception("Vault decrypt failed for user=%s service=%s", user_id, service)
            return None
        metadata = json.loads(row["metadata"]) if row.get("metadata") else {}
        return {"secret": secret, "metadata": metadata}

    async def list_keys(self, user_id: str) -> List[Dict[str, Any]]:
        rows = await self.store.list_keys(user_id)
        result = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row.get("metadata") else {}
            result.append({
                "service": row["service"],
                "last4": metadata.get("_last4", "????"),
                "created_at": row["created_at"],
                "last_validated_at": row.get("last_validated_at"),
            })
        return result

    async def delete_key(self, user_id: str, service: str) -> None:
        await self.store.delete_key(user_id, service)


def get_vault_service() -> VaultService:
    global _shared_service
    if _shared_service is None:
        _shared_service = VaultService(VaultKeyStore())
    return _shared_service

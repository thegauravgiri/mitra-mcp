"""PostgreSQL persistence for envelope-encrypted per-user third-party API keys.

Mirrors the connect-per-call pattern used by PostgresOAuthCredentialStore —
no connection pool, lazy table creation on first use.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from mitra.core.oauth_store import PostgresOAuthCredentialStore

logger = logging.getLogger("mitra.core.vault_store")


class VaultKeyStore:
    """PostgreSQL-backed storage for wrapped-DEK-encrypted third-party API keys."""

    def __init__(self, dsn: Optional[str] = None):
        raw_dsn = dsn or os.environ.get("DATABASE_URL")
        if not raw_dsn:
            raise ValueError(
                "PostgreSQL connection string is required. "
                "Set the DATABASE_URL environment variable or pass dsn to the constructor."
            )
        self.dsn = PostgresOAuthCredentialStore._format_dsn(raw_dsn)
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS vault_keys (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        service TEXT NOT NULL,
                        wrapped_dek BYTEA NOT NULL,
                        ciphertext BYTEA NOT NULL,
                        nonce BYTEA NOT NULL,
                        kms_key_version TEXT NOT NULL,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_validated_at TEXT,
                        UNIQUE(user_id, service)
                    )
                    """
                )
                await conn.commit()
            self._initialized = True
        except Exception:
            logger.exception("Failed to initialize vault_keys table.")
            raise

    async def save_key(
        self,
        user_id: str,
        service: str,
        wrapped_dek: bytes,
        ciphertext: bytes,
        nonce: bytes,
        kms_key_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        row_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata) if metadata else None
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                """
                INSERT INTO vault_keys
                    (id, user_id, service, wrapped_dek, ciphertext, nonce, kms_key_version,
                     metadata, created_at, updated_at, last_validated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, service) DO UPDATE SET
                    wrapped_dek = EXCLUDED.wrapped_dek,
                    ciphertext = EXCLUDED.ciphertext,
                    nonce = EXCLUDED.nonce,
                    kms_key_version = EXCLUDED.kms_key_version,
                    metadata = EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at,
                    last_validated_at = EXCLUDED.last_validated_at
                """,
                (
                    row_id, user_id, service.lower(), wrapped_dek, ciphertext, nonce,
                    kms_key_version, metadata_json, now, now, now,
                ),
            )
            await conn.commit()

    async def get_key_row(self, user_id: str, service: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "SELECT * FROM vault_keys WHERE user_id = %s AND service = %s",
                (user_id, service.lower()),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_keys(self, user_id: str) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "SELECT service, metadata, created_at, last_validated_at "
                "FROM vault_keys WHERE user_id = %s ORDER BY service",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_key(self, user_id: str, service: str) -> None:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                "DELETE FROM vault_keys WHERE user_id = %s AND service = %s",
                (user_id, service.lower()),
            )
            await conn.commit()

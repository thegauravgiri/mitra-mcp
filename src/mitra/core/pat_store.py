"""PostgreSQL persistence for user-generated MCP personal access tokens.

These are a header-based fallback for clients that can't do the OAuth
authorize/token dance (see authserver_routes.py) — a user signed into the
vault can mint one here and paste it into any client as a plain
`Authorization: Bearer <token>` header. Only the SHA-256 hash is stored, not
the raw token, since a leaked database shouldn't hand out working
credentials (same reasoning as the vault's envelope-encrypted API keys).
"""
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from mitra.core.oauth_store import PostgresOAuthCredentialStore

logger = logging.getLogger("mitra.core.pat_store")

TOKEN_PREFIX = "mitra_pat_"


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class PersonalTokenStore:
    """PostgreSQL-backed storage for hashed MCP personal access tokens."""

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
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_personal_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    label TEXT,
                    last4 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    revoked BOOLEAN NOT NULL DEFAULT FALSE
                )
                """
            )
            await conn.commit()
        self._initialized = True

    async def create_token(self, user_id: str, label: Optional[str] = None) -> str:
        """Generates, stores, and returns a new raw token. Shown to the user exactly once."""
        await self._ensure_initialized()
        raw_token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        row_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                """
                INSERT INTO mcp_personal_tokens (id, user_id, token_hash, label, last4, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (row_id, user_id, _hash_token(raw_token), label, raw_token[-4:], now),
            )
            await conn.commit()
        return raw_token

    async def list_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "SELECT id, label, last4, created_at, last_used_at FROM mcp_personal_tokens "
                "WHERE user_id = %s AND revoked = FALSE ORDER BY created_at DESC",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def revoke_token(self, user_id: str, token_id: str) -> None:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                "UPDATE mcp_personal_tokens SET revoked = TRUE WHERE id = %s AND user_id = %s",
                (token_id, user_id),
            )
            await conn.commit()

    async def resolve_user_id(self, raw_token: str) -> Optional[str]:
        """Validates a raw bearer token and returns the owning user_id, or None."""
        await self._ensure_initialized()
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc).isoformat()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "SELECT id, user_id FROM mcp_personal_tokens WHERE token_hash = %s AND revoked = FALSE",
                (token_hash,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            await conn.execute(
                "UPDATE mcp_personal_tokens SET last_used_at = %s WHERE id = %s",
                (now, row["id"]),
            )
            await conn.commit()
            return row["user_id"]


_shared_store: Optional[PersonalTokenStore] = None


def get_pat_store() -> PersonalTokenStore:
    global _shared_store
    if _shared_store is None:
        _shared_store = PersonalTokenStore()
    return _shared_store

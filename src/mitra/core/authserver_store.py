"""PostgreSQL persistence for the MCP OAuth authorization-server proxy.

Mitra acts as its own OAuth 2.1 authorization server towards MCP clients
(so they get a normal "click connect -> pick your Google account -> done"
flow with Dynamic Client Registration) while delegating actual identity
proof to Google underneath. This module stores the three pieces of state
that flow needs: registered clients (from DCR), single-use authorization
codes (PKCE-bound), and long-lived refresh tokens.

Postgres-backed (not in-memory) because Cloud Run can and does run more
than one instance — an authorize/token round trip may land on a different
instance than the one that started it.
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

logger = logging.getLogger("mitra.core.authserver_store")


class AuthServerStore:
    """PostgreSQL-backed storage for OAuth clients, auth codes, and refresh tokens."""

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
                CREATE TABLE IF NOT EXISTS oauth_clients (
                    client_id TEXT PRIMARY KEY,
                    redirect_uris TEXT NOT NULL,
                    client_name TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_login_requests (
                    login_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    client_state TEXT,
                    code_challenge TEXT NOT NULL,
                    code_challenge_method TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_auth_codes (
                    code TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    code_challenge TEXT NOT NULL,
                    code_challenge_method TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    used BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
                    token TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    revoked BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.commit()
        self._initialized = True

    # ── Clients (Dynamic Client Registration) ───────────────────────────────

    async def register_client(self, client_id: str, redirect_uris: List[str], client_name: Optional[str]) -> None:
        await self._ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                "INSERT INTO oauth_clients (client_id, redirect_uris, client_name, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (client_id, json.dumps(redirect_uris), client_name, now),
            )
            await conn.commit()

    async def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "SELECT client_id, redirect_uris, client_name FROM oauth_clients WHERE client_id = %s",
                (client_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            row = dict(row)
            row["redirect_uris"] = json.loads(row["redirect_uris"])
            return row

    # ── Pending login requests (bridges the client's /authorize call to the
    #    Google callback, since Google's own `state` slot is used for this) ──

    async def save_login_request(
        self,
        login_id: str,
        client_id: str,
        redirect_uri: str,
        client_state: Optional[str],
        code_challenge: str,
        code_challenge_method: str,
        ttl_seconds: int,
    ) -> None:
        await self._ensure_initialized()
        now = datetime.now(timezone.utc)
        expires_at = now.timestamp() + ttl_seconds
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                """
                INSERT INTO oauth_login_requests
                    (login_id, client_id, redirect_uri, client_state, code_challenge,
                     code_challenge_method, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    login_id, client_id, redirect_uri, client_state, code_challenge,
                    code_challenge_method, now.isoformat(),
                    datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
                ),
            )
            await conn.commit()

    async def pop_login_request(self, login_id: str) -> Optional[Dict[str, Any]]:
        """Fetches and deletes a login request (single use)."""
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "SELECT * FROM oauth_login_requests WHERE login_id = %s", (login_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            await conn.execute("DELETE FROM oauth_login_requests WHERE login_id = %s", (login_id,))
            await conn.commit()
            row = dict(row)
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
                return None
            return row

    # ── Authorization codes ─────────────────────────────────────────────────

    async def save_auth_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        user_id: str,
        ttl_seconds: int,
    ) -> None:
        await self._ensure_initialized()
        now = datetime.now(timezone.utc)
        expires_at = now.timestamp() + ttl_seconds
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                """
                INSERT INTO oauth_auth_codes
                    (code, client_id, redirect_uri, code_challenge, code_challenge_method,
                     user_id, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code, client_id, redirect_uri, code_challenge, code_challenge_method,
                    user_id, now.isoformat(),
                    datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
                ),
            )
            await conn.commit()

    async def consume_auth_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Atomically marks a code used and returns its row, or None if invalid/used/expired."""
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "UPDATE oauth_auth_codes SET used = TRUE "
                "WHERE code = %s AND used = FALSE RETURNING *",
                (code,),
            )
            row = await cursor.fetchone()
            await conn.commit()
            if not row:
                return None
            row = dict(row)
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
                return None
            return row

    # ── Refresh tokens ───────────────────────────────────────────────────────

    async def save_refresh_token(self, token: str, client_id: str, user_id: str) -> None:
        await self._ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                "INSERT INTO oauth_refresh_tokens (token, client_id, user_id, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (token, client_id, user_id, now),
            )
            await conn.commit()

    async def get_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
            cursor = await conn.execute(
                "SELECT * FROM oauth_refresh_tokens WHERE token = %s AND revoked = FALSE",
                (token,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def revoke_refresh_token(self, token: str) -> None:
        await self._ensure_initialized()
        async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
            await conn.execute(
                "UPDATE oauth_refresh_tokens SET revoked = TRUE WHERE token = %s", (token,)
            )
            await conn.commit()


_shared_store: Optional[AuthServerStore] = None


def get_authserver_store() -> AuthServerStore:
    global _shared_store
    if _shared_store is None:
        _shared_store = AuthServerStore()
    return _shared_store

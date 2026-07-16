"""OAuth Credential Store interfaces and PostgreSQL database persistence."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import os
import uuid
from typing import Optional, Dict, Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("mitra.core.oauth_store")


class OAuthCredentialStore(ABC):
    """Abstract Base Class defining the storage interface for OAuth Credentials."""

    @abstractmethod
    async def get_credential(self, user_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Retrieves credentials for the specified user and provider.

        Returns:
            A dict with access_token, refresh_token, expires_at, etc., or None if not found.
        """
        pass

    @abstractmethod
    async def save_credential(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> None:
        """Saves or updates credentials for the specified user and provider."""
        pass

    @abstractmethod
    async def delete_credential(self, user_id: str, provider: str) -> None:
        """Deletes credentials for the specified user and provider."""
        pass


class PostgresOAuthCredentialStore(OAuthCredentialStore):
    """PostgreSQL-backed implementation of OAuthCredentialStore."""

    @staticmethod
    def _format_dsn(dsn: str) -> str:
        """Preprocesses the DSN/connection URI to safely URL-encode credentials if present.
        
        This prevents connection errors when passwords contain special characters like slashes.
        """
        if not dsn.startswith(("postgresql://", "postgres://")):
            return dsn
        if "@" not in dsn:
            return dsn

        try:
            scheme, rest = dsn.split("://", 1)
            credentials, host_port_db = rest.rsplit("@", 1)
            
            if ":" in credentials:
                user, password = credentials.split(":", 1)
                import urllib.parse
                encoded_user = urllib.parse.quote(user, safe="")
                encoded_password = urllib.parse.quote(password, safe="")
                return f"{scheme}://{encoded_user}:{encoded_password}@{host_port_db}"
            else:
                import urllib.parse
                encoded_user = urllib.parse.quote(credentials, safe="")
                return f"{scheme}://{encoded_user}@{host_port_db}"
        except Exception:
            # Fall back to original DSN if parsing fails
            return dsn

    def __init__(self, dsn: Optional[str] = None):
        """Initializes the PostgreSQL credential store.

        Args:
            dsn: PostgreSQL connection string. Defaults to DATABASE_URL env var.
        """
        raw_dsn = dsn or os.environ.get("DATABASE_URL")
        if not raw_dsn:
            raise ValueError(
                "PostgreSQL connection string is required. "
                "Set the DATABASE_URL environment variable or pass dsn to the constructor."
            )
        self.dsn = self._format_dsn(raw_dsn)
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazily creates the credentials table if it does not exist."""
        if self._initialized:
            return
        try:
            async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS credentials (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        access_token TEXT NOT NULL,
                        refresh_token TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(user_id, provider)
                    )
                """)
                await conn.commit()
            self._initialized = True
        except Exception:
            logger.exception("Failed to initialize PostgreSQL database credentials table.")
            raise

    async def get_credential(self, user_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Retrieves credentials from PostgreSQL database."""
        await self._ensure_initialized()
        try:
            async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:
                cursor = await conn.execute(
                    "SELECT id, user_id, provider, access_token, refresh_token, expires_at, created_at, updated_at "
                    "FROM credentials WHERE user_id = %s AND provider = %s",
                    (user_id, provider.lower())
                )
                row = await cursor.fetchone()
                if row:
                    return dict(row)
        except Exception:
            logger.exception(f"Failed to fetch credential for user {user_id} and provider {provider}")
            raise
        return None

    async def save_credential(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> None:
        """Saves or updates credentials in the PostgreSQL database."""
        await self._ensure_initialized()
        now_str = datetime.now(timezone.utc).isoformat()
        expires_str = expires_at.isoformat()
        row_id = str(uuid.uuid4())

        try:
            async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
                await conn.execute(
                    """
                    INSERT INTO credentials (id, user_id, provider, access_token, refresh_token, expires_at, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(user_id, provider) DO UPDATE SET
                        access_token = EXCLUDED.access_token,
                        refresh_token = EXCLUDED.refresh_token,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (row_id, user_id, provider.lower(), access_token, refresh_token, expires_str, now_str, now_str)
                )
                await conn.commit()
        except Exception:
            logger.exception(f"Failed to save credential for user {user_id} and provider {provider}")
            raise

    async def delete_credential(self, user_id: str, provider: str) -> None:
        """Deletes credentials from PostgreSQL database."""
        await self._ensure_initialized()
        try:
            async with await psycopg.AsyncConnection.connect(self.dsn) as conn:
                await conn.execute(
                    "DELETE FROM credentials WHERE user_id = %s AND provider = %s",
                    (user_id, provider.lower())
                )
                await conn.commit()
        except Exception:
            logger.exception(f"Failed to delete credential for user {user_id} and provider {provider}")
            raise

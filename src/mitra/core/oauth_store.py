"""OAuth Credential Store interfaces and SQLite database persistence."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import os
import sqlite3
import uuid
from typing import Optional, Dict, Any

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


class SQLiteOAuthCredentialStore(OAuthCredentialStore):
    """SQLite-backed implementation of OAuthCredentialStore."""

    def __init__(self, db_path: Optional[str] = None):
        """Initializes the SQLite database.

        Args:
            db_path: Path to SQLite file. Defaults to MITRA_DB_PATH or 'mitra.db'.
        """
        self.db_path = db_path or os.environ.get("MITRA_DB_PATH", "mitra.db")
        self._init_db()

    def _init_db(self) -> None:
        """Creates the credentials table if it does not exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
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
                conn.commit()
        except Exception:
            logger.exception("Failed to initialize SQLite database credentials table.")
            raise

    async def get_credential(self, user_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """Retrieves credentials from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT id, user_id, provider, access_token, refresh_token, expires_at, created_at, updated_at "
                    "FROM credentials WHERE user_id = ? AND provider = ?",
                    (user_id, provider.lower())
                )
                row = cursor.fetchone()
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
        """Saves or updates credentials in the SQLite database."""
        now_str = datetime.now(timezone.utc).isoformat()
        expires_str = expires_at.isoformat()
        row_id = str(uuid.uuid4())

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO credentials (id, user_id, provider, access_token, refresh_token, expires_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, provider) DO UPDATE SET
                        access_token = excluded.access_token,
                        refresh_token = excluded.refresh_token,
                        expires_at = excluded.expires_at,
                        updated_at = excluded.updated_at
                    """,
                    (row_id, user_id, provider.lower(), access_token, refresh_token, expires_str, now_str, now_str)
                )
                conn.commit()
        except Exception:
            logger.exception(f"Failed to save credential for user {user_id} and provider {provider}")
            raise

    async def delete_credential(self, user_id: str, provider: str) -> None:
        """Deletes credentials from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM credentials WHERE user_id = ? AND provider = ?",
                    (user_id, provider.lower())
                )
                conn.commit()
        except Exception:
            logger.exception(f"Failed to delete credential for user {user_id} and provider {provider}")
            raise

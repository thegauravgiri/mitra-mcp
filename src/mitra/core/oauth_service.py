"""OAuth token refresher and credentials management services."""

from abc import ABC, abstractmethod
import datetime
from datetime import timezone
import logging
from typing import Optional, Dict, Tuple
import httpx

from mitra.core.crypto import TokenEncryption
from mitra.core.oauth_store import OAuthCredentialStore

logger = logging.getLogger("mitra.core.oauth_service")


class TokenRefresher(ABC):
    """Abstract class for refreshing OAuth Access Tokens."""

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Tuple[str, Optional[str], int]:
        """Refreshes the credentials and returns the new tokens.

        Returns:
            A tuple of (access_token, new_refresh_token, expires_in_seconds).
            new_refresh_token should be None if Google/provider did not rotate the refresh token.
        """
        pass


class GoogleTokenRefresher(TokenRefresher):
    """Google-specific OAuth Token Refresher."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    async def refresh_token(self, refresh_token: str) -> Tuple[str, Optional[str], int]:
        """Sends refresh token requests to Google OAuth."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Google Client ID or Client Secret is not configured.")

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post("https://oauth2.googleapis.com/token", data=payload, timeout=10.0)
                if resp.status_code != 200:
                    logger.error(f"Google Token refresh failed: {resp.text}")
                    # Check if refresh token was revoked/invalidated
                    if resp.status_code == 400:
                        raise ValueError(f"Google refresh token has been revoked or is invalid: {resp.text}")
                    raise RuntimeError(f"Failed to refresh Google token: {resp.text}")
                
                data = resp.json()
                return data["access_token"], data.get("refresh_token"), data["expires_in"]
            except httpx.HTTPError as e:
                raise RuntimeError(f"HTTP request to Google token endpoint failed: {str(e)}")


class CredentialService:
    """Orchestrates loading, checking expiration, automatic refreshing, and token encryption."""

    def __init__(self, store: OAuthCredentialStore, encryption: TokenEncryption):
        self.store = store
        self.encryption = encryption
        self.refreshers: Dict[str, TokenRefresher] = {}

    def register_refresher(self, provider: str, refresher: TokenRefresher) -> None:
        """Registers a refresher instance for an OAuth provider."""
        self.refreshers[provider.lower()] = refresher

    async def get_valid_access_token(self, user_id: str, provider: str) -> str:
        """Retrieves a valid access token for the given user and provider.

        If the token is expired or close to expiration (within 60 seconds), it automatically
        refreshes the token using the registered refresher, updates the database, and returns the new token.
        """
        provider_key = provider.lower()
        cred = await self.store.get_credential(user_id, provider_key)
        if not cred:
            raise ValueError(f"{provider.capitalize()} Calendar has not been connected for this account.")

        now = datetime.datetime.now(timezone.utc)
        try:
            expires_at = datetime.datetime.fromisoformat(cred["expires_at"])
        except ValueError:
            logger.error(f"Invalid timestamp in expires_at for user {user_id}: {cred['expires_at']}")
            # Treat as expired if unparseable
            expires_at = now - datetime.timedelta(seconds=1)

        # Buffer of 60 seconds
        if expires_at <= now + datetime.timedelta(seconds=60):
            logger.info(f"Access token for user {user_id} and provider {provider} is expired; refreshing...")
            refresher = self.refreshers.get(provider_key)
            if not refresher:
                raise ValueError(f"No token refresher registered for provider: {provider}")

            # Decrypt the stored refresh token
            encrypted_refresh = cred["refresh_token"]
            try:
                decrypted_refresh = self.encryption.decrypt(encrypted_refresh)
            except Exception as e:
                logger.exception("Failed to decrypt stored refresh token.")
                raise ValueError("Stored refresh token is corrupted or key mismatch.")

            # Refresh
            try:
                new_acc, new_ref, expires_in = await refresher.refresh_token(decrypted_refresh)
            except ValueError:
                # Refresh token was revoked, clean up credential store and prompt re-auth
                logger.warning(f"Refresh token invalid/revoked for user {user_id}. Deleting credentials.")
                await self.store.delete_credential(user_id, provider_key)
                raise

            # Save updated credentials
            new_expires = now + datetime.timedelta(seconds=expires_in)
            final_refresh = new_ref or decrypted_refresh
            encrypted_final_refresh = self.encryption.encrypt(final_refresh)

            await self.store.save_credential(
                user_id=user_id,
                provider=provider_key,
                access_token=new_acc,
                refresh_token=encrypted_final_refresh,
                expires_at=new_expires,
            )
            return new_acc

        return cred["access_token"]


_shared_service: Optional[CredentialService] = None


def get_credential_service() -> CredentialService:
    """Lazily instantiates and returns the shared global CredentialService."""
    global _shared_service
    if _shared_service is None:
        import os
        from mitra.core.crypto import TokenEncryption
        from mitra.core.oauth_store import SQLiteOAuthCredentialStore

        encryption = TokenEncryption()
        store = SQLiteOAuthCredentialStore()
        _shared_service = CredentialService(store, encryption)

        # Automatically register Google refresher if environment configuration is present
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        refresher = GoogleTokenRefresher(client_id, client_secret)
        _shared_service.register_refresher("google", refresher)

    return _shared_service

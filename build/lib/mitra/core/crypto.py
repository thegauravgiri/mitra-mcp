"""Symmetric encryption and decryption utilities for stored tokens."""

import logging
import os
from typing import Optional
from cryptography.fernet import Fernet

logger = logging.getLogger("mitra.core.crypto")


class TokenEncryption:
    """Helper class to encrypt and decrypt sensitive fields using Fernet symmetric encryption."""

    def __init__(self, key: Optional[str] = None):
        """Initializes the encryption handler.

        Args:
            key: Base64 encoded 32-byte key. If None, falls back to GOOGLE_ENCRYPTION_KEY.
        """
        enc_key = key or os.environ.get("GOOGLE_ENCRYPTION_KEY")
        if not enc_key:
            logger.warning(
                "GOOGLE_ENCRYPTION_KEY environment variable is not configured. "
                "Generating a temporary encryption key for this session. "
                "WARNING: Saved tokens will not be decryptable after server restart!"
            )
            # Generate a temporary key for the session so it doesn't crash on start
            enc_key = Fernet.generate_key().decode()

        try:
            self.fernet = Fernet(enc_key.encode())
        except Exception as e:
            logger.exception("Failed to initialize Fernet token encryption.")
            raise ValueError(f"Invalid GOOGLE_ENCRYPTION_KEY provided: {str(e)}")

    def encrypt(self, plaintext: str) -> str:
        """Encrypts a plaintext string."""
        if not plaintext:
            return ""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypts a ciphertext string back to plaintext."""
        if not ciphertext:
            return ""
        return self.fernet.decrypt(ciphertext.encode()).decode()

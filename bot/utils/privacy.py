"""Privacy helpers for operational identifiers."""

import hashlib
import hmac

from bot.config import settings

__all__ = ['pseudonymize_user_id']


def pseudonymize_user_id(user_id: int) -> str:
    """Return a stable keyed pseudonym for Telegram user ID."""
    key = settings.encryption_key.get_secret_value()
    return hmac.new(
        key.encode('utf-8'),
        str(user_id).encode('ascii'),
        hashlib.sha256,
    ).hexdigest()[:16]

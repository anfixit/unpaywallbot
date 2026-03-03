"""Методы обхода paywall."""

from bot.services.methods.archive_relay import (
    fetch_via_archive,
)
from bot.services.methods.googlebot_spoof import (
    fetch_via_googlebot_spoof,
)
from bot.services.methods.headless_auth import (
    fetch_via_headless_auth,
)
from bot.services.methods.js_disable import (
    fetch_via_js_disable,
)

__all__ = [
    'fetch_via_archive',
    'fetch_via_googlebot_spoof',
    'fetch_via_headless_auth',
    'fetch_via_js_disable',
]

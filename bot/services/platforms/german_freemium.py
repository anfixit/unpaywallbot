"""Платформа для немецких freemium-изданий.

Особенности:
- Spiegel S+, Zeit Z+, FAZ F+, Süddeutsche, Tagesspiegel
- Статья может быть частично открыта, но требует проверки маркеров
- Некоторые используют параметр ?reduced=true для полного текста
"""

import re
from urllib.parse import parse_qs, urlencode, urlparse

from bot.auth.account_manager import AccountManager
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.services.content_extractor import ContentExtractor
from bot.services.methods.headless_auth import fetch_via_headless_auth
from bot.services.methods.js_disable import fetch_via_js_disable

__all__ = ['GermanFreemiumPlatform']


class GermanFreemiumPlatform:
    """Обработчик немецких freemium-изданий."""

    # Маркеры премиум-контента в URL
    PREMIUM_URL_PATTERNS = {
        'spiegel.de': r'/plus/|spiegel-plus|s\+',
        'zeit.de': r'/plus/|zeit-plus|z\+',
        'faz.net': r'/faz-plus|f\+',
        'sueddeutsche.de': r'plus|reduced=true',
        'tagesspiegel.de': r'/plus/',
        'welt.de': r'/plus/',
    }

    # Маркеры в HTML (если URL не помог)
    PREMIUM_HTML_PATTERNS = [
        r'class="[^"]*paywall[^"]*"',
        r'class="[^"]*premium[^"]*"',
        r'data-.*=."paywall"',
        r'id="[^"]*paywall[^"]*"',
    ]

    def __init__(
        self,
        extractor: ContentExtractor | None = None,
        account_manager: AccountManager | None = None,
    ) -> None:
        """Инициализировать платформу."""
        self.extractor = extractor or ContentExtractor()
        self.account_manager = account_manager

    async def handle(
        self,
        url: str,
        paywall_info: PaywallInfo,
        user_id: int | None = None,
    ) -> Article | None:
        """Обработать URL немецкого издания.

        Args:
            url: URL статьи.
            paywall_info: Информация о paywall.
            user_id: ID пользователя (для авторизации).

        Returns:
            Article или None.
        """
        # Проверяем, является ли статья премиум-контентом
        is_premium = self._check_if_premium(url, paywall_info.domain)

        if not is_premium:
            # Открытая статья — просто забираем через js_disable
            return await fetch_via_js_disable(url, extractor=self.extractor)

        # Премиум-статья — пробуем получить через авторизацию
        if user_id and self.account_manager:
            # Пробуем через headless с авторизацией
            try:
                return await fetch_via_headless_auth(
                    url,
                    user_id=user_id,
                    account_manager=self.account_manager,
                    extractor=self.extractor,
                )
            except Exception:
                # Если не вышло, пробуем archive.ph как fallback
                from bot.services.methods.archive_relay import (
                    fetch_via_archive,
                )
                return await fetch_via_archive(url, extractor=self.extractor)

        # Нет аккаунта — может, сработает ?reduced=true
        if 'sueddeutsche.de' in paywall_info.domain:
            modified_url = self._add_reduced_param(url)
            return await fetch_via_js_disable(modified_url, extractor=self.extractor)

        return None

    def _check_if_premium(self, url: str, domain: str) -> bool:
        """Проверить, является ли статья премиум-контентом."""
        # 1. Проверяем по URL
        for pattern_domain, pattern in self.PREMIUM_URL_PATTERNS.items():
            if pattern_domain in domain:
                if re.search(pattern, url, re.IGNORECASE):
                    return True
                break

        # 2. По умолчанию считаем, что статья открытая
        # (полноценная проверка по HTML требует отдельного запроса)
        return False

    def _add_reduced_param(self, url: str) -> str:
        """Добавить параметр ?reduced=true для Süddeutsche."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query['reduced'] = ['true']

        new_query = urlencode(query, doseq=True)
        return parsed._replace(query=new_query).geturl()

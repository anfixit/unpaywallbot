"""Платформа для Republic.io.

Особенности:
- Hard paywall с антибот-защитой
- Требует авторизации
- Использует headless браузер
"""


from bot.auth.account_manager import AccountManager
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.services.content_extractor import ContentExtractor
from bot.services.methods.headless_auth import fetch_via_headless_auth

__all__ = ['RepublicPlatform']


class RepublicPlatform:
    """Обработчик Republic.io."""

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
        """Обработать URL Republic.io.

        Только через headless с авторизацией.

        Args:
            url: URL статьи.
            paywall_info: Информация о paywall.
            user_id: ID пользователя Telegram.

        Returns:
            Article или None.

        Raises:
            RuntimeError: Если нет аккаунта или user_id.
        """
        if not user_id:
            raise RuntimeError('Republic.io требует user_id для авторизации')

        if not self.account_manager:
            raise RuntimeError('Republic.io требует account_manager')

        return await fetch_via_headless_auth(
            url,
            user_id=user_id,
            account_manager=self.account_manager,
            extractor=self.extractor,
        )

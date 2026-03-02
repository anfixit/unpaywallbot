"""Модель данных о типе paywall для конкретного URL.

Содержит результат классификации, который используется
оркестратором для выбора метода обхода.
"""

from dataclasses import dataclass, field
from typing import Optional

from bot.constants import BypassMethod, PaywallType

__all__ = ['PaywallInfo']


@dataclass
class PaywallInfo:
    """Информация о типе paywall для конкретного URL.

    Создаётся классификатором на основе домена и содержимого
    страницы (если уже был сделан запрос).
    """

    # --- Обязательные поля ---
    url: str
    """Оригинальный URL (нормализованный)."""

    domain: str
    """Домен из URL (извлечённый extract_domain)."""

    # --- Тип и метод (могут быть неизвестны) ---
    paywall_type: PaywallType = PaywallType.UNKNOWN
    """Тип paywall (soft/metered/hard/freemium/unknown)."""

    suggested_method: Optional[BypassMethod] = None
    """Предполагаемый метод обхода (если известен)."""

    # --- Платформенная специфика ---
    platform: Optional[str] = None
    """Имя платформы для специфичной обработки (например, 'german_freemium')."""

    # --- Детали для методов ---
    requires_auth: bool = False
    """Требуется ли авторизация (аккаунт) для доступа."""

    requires_headless: bool = False
    """Требуется ли headless-браузер (для hard paywall)."""

    # --- Служебные поля ---
    classified_at: datetime = field(default_factory=datetime.now)
    """Время классификации (UTC)."""

    confidence: float = 1.0
    """Уверенность в классификации (0.0 - 1.0)."""

    @classmethod
    def unknown(cls, url: str) -> 'PaywallInfo':
        """Создать запись для неизвестного типа paywall.

        Используется как fallback, когда классификация не удалась.
        """
        from bot.utils.url_utils import extract_domain

        return cls(
            url=url,
            domain=extract_domain(url),
            paywall_type=PaywallType.UNKNOWN,
            suggested_method=None,
        )

    @property
    def is_known(self) -> bool:
        """Известен ли тип paywall."""
        return self.paywall_type != PaywallType.UNKNOWN

    @property
    def can_bypass(self) -> bool:
        """Можно ли потенциально обойти (есть метод)."""
        return self.suggested_method is not None

    def __str__(self) -> str:
        """Краткое представление для логов."""
        return (
            f'PaywallInfo('
            f'domain={self.domain}, '
            f'type={self.paywall_type}, '
            f'method={self.suggested_method})'
        )

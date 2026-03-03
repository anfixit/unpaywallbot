"""Классификатор paywall по домену и URL.

Загружает конфигурацию из data/paywall_map.yaml
и определяет тип paywall для переданного URL.
"""

import asyncio
import logging
from pathlib import Path
from typing import Final

import yaml

from bot.constants import BypassMethod, PaywallType
from bot.models.paywall_info import PaywallInfo
from bot.utils.url_utils import extract_domain

__all__ = ['PaywallClassifier']

logger = logging.getLogger(__name__)

CONFIG_PATH: Final[Path] = (
    Path(__file__).parent.parent.parent
    / 'data'
    / 'paywall_map.yaml'
)


class PaywallClassifier:
    """Классификатор paywall на основе YAML-конфига.

    Загружает маппинг доменов → тип paywall
    и рекомендуемый метод обхода.
    """

    def __init__(
        self,
        config_path: Path = CONFIG_PATH,
    ) -> None:
        """Инициализировать с загрузкой конфига.

        Args:
            config_path: Путь к YAML-файлу.

        Raises:
            FileNotFoundError: Файл не существует.
            yaml.YAMLError: Некорректный YAML.
        """
        self.config_path = config_path
        self._domain_map: dict[str, dict] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Загрузить и распарсить YAML."""
        if not self.config_path.exists():
            msg = (
                'Конфиг paywall не найден: '
                f'{self.config_path}'
            )
            raise FileNotFoundError(msg)

        with open(
            self.config_path, encoding='utf-8',
        ) as f:
            raw_config = yaml.safe_load(f)

        if not isinstance(raw_config, dict):
            msg = (
                'Неверный формат конфига: '
                f'ожидался dict, получен '
                f'{type(raw_config).__name__}'
            )
            raise ValueError(msg)

        self._domain_map = raw_config
        logger.info(
            'Загружено %d доменов из конфига',
            len(self._domain_map),
        )

    def _match_domain(
        self,
        domain: str,
    ) -> tuple[str, dict] | None:
        """Найти запись по домену (с поддоменами).

        Args:
            domain: Домен (например, 'spiegel.de').

        Returns:
            (ключ, конфиг) или None.
        """
        if domain in self._domain_map:
            return domain, self._domain_map[domain]

        parts = domain.split('.')
        for i in range(1, len(parts) - 1):
            test = '.'.join(parts[i:])
            if test in self._domain_map:
                return test, self._domain_map[test]

        return None

    @staticmethod
    def _parse_paywall_type(
        type_str: str,
    ) -> PaywallType:
        """Строка из конфига → PaywallType."""
        try:
            return PaywallType(type_str)
        except ValueError:
            return PaywallType.UNKNOWN

    @staticmethod
    def _parse_bypass_method(
        method_str: str | None,
    ) -> BypassMethod | None:
        """Строка из конфига → BypassMethod."""
        if not method_str:
            return None
        try:
            return BypassMethod(method_str)
        except ValueError:
            return None

    async def classify(self, url: str) -> PaywallInfo:
        """Определить тип paywall для URL.

        Args:
            url: Полный URL статьи.

        Returns:
            PaywallInfo с результатами.
        """
        domain = extract_domain(url)
        match = self._match_domain(domain)

        if not match:
            return PaywallInfo.unknown(url)

        _domain_key, config = match

        paywall_type = self._parse_paywall_type(
            config.get('type', 'unknown'),
        )
        suggested_method = self._parse_bypass_method(
            config.get('method'),
        )

        requires_auth = config.get(
            'requires_auth', False,
        )
        requires_headless = config.get(
            'requires_headless', False,
        )

        if paywall_type == PaywallType.HARD:
            requires_headless = True
            requires_auth = True

        platform = config.get('platform')

        return PaywallInfo(
            url=url,
            domain=domain,
            paywall_type=paywall_type,
            suggested_method=suggested_method,
            platform=platform,
            requires_auth=requires_auth,
            requires_headless=requires_headless,
            confidence=1.0,
        )

    def reload(self) -> None:
        """Перезагрузить конфигурацию (синхронно)."""
        self._load_config()

    async def reload_async(self) -> None:
        """Перезагрузить конфигурацию (async-safe).

        Файловый I/O через to_thread (§17.1).
        """
        await asyncio.to_thread(self._load_config)

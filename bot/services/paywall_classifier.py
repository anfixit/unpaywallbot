"""Классификатор paywall по домену и URL.

Загружает конфигурацию из data/paywall_map.yaml и определяет
тип paywall для переданного URL. Используется оркестратором
для выбора стратегии обхода.
"""

from pathlib import Path
from typing import Final

import yaml

from bot.constants import BypassMethod, PaywallType
from bot.models.paywall_info import PaywallInfo
from bot.utils.url_utils import extract_domain

__all__ = ['PaywallClassifier']

# Путь к файлу конфигурации относительно корня проекта
CONFIG_PATH: Final[Path] = Path(__file__).parent.parent.parent / 'data' / 'paywall_map.yaml'


class PaywallClassifier:
    """Классификатор paywall на основе YAML-конфигурации.

    Загружает маппинг доменов в тип paywall и рекомендуемый метод обхода.
    Результат возвращает в виде модели PaywallInfo.
    """

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        """Инициализировать классификатор с загрузкой конфига.

        Args:
            config_path: Путь к YAML-файлу с конфигурацией.

        Raises:
            FileNotFoundError: Если файл конфигурации не существует.
            yaml.YAMLError: Если файл содержит некорректный YAML.
        """
        self.config_path = config_path
        self._domain_map: dict[str, dict] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Загрузить и распарсить YAML-конфигурацию."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f'Конфиг paywall не найден: {self.config_path}'
            )

        with open(self.config_path, encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)

        if not isinstance(raw_config, dict):
            raise ValueError(
                f'Неверный формат конфига: ожидался dict, получен {type(raw_config)}'
            )

        self._domain_map = raw_config

    def _match_domain(self, domain: str) -> tuple[str, dict] | None:
        """Найти запись в конфиге по домену (с поддержкой поддоменов).

        Args:
            domain: Домен для поиска (например, 'spiegel.de').

        Returns:
            Кортеж (найденный_ключ, конфиг) или None, если не найден.
        """
        # Прямое совпадение
        if domain in self._domain_map:
            return domain, self._domain_map[domain]

        # Проверяем поддомены (например, для www.spiegel.de -> spiegel.de)
        parts = domain.split('.')
        for i in range(1, len(parts) - 1):
            test_domain = '.'.join(parts[i:])
            if test_domain in self._domain_map:
                return test_domain, self._domain_map[test_domain]

        return None

    def _parse_paywall_type(self, type_str: str) -> PaywallType:
        """Преобразовать строку из конфига в PaywallType.

        Args:
            type_str: Строка из поля 'type' в YAML.

        Returns:
            Соответствующий элемент PaywallType или UNKNOWN.
        """
        try:
            return PaywallType(type_str)
        except ValueError:
            return PaywallType.UNKNOWN

    def _parse_bypass_method(self, method_str: str | None) -> BypassMethod | None:
        """Преобразовать строку из конфига в BypassMethod.

        Args:
            method_str: Строка из поля 'method' в YAML или None.

        Returns:
            Соответствующий элемент BypassMethod или None.
        """
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
            PaywallInfo с результатами классификации.
        """
        domain = extract_domain(url)

        # Ищем в конфиге
        match = self._match_domain(domain)

        if not match:
            # Неизвестный домен
            return PaywallInfo.unknown(url)

        domain_key, config = match

        # Парсим тип и метод
        paywall_type = self._parse_paywall_type(config.get('type', 'unknown'))
        method_str = config.get('method')
        suggested_method = self._parse_bypass_method(method_str)

        # Определяем requires_auth / requires_headless
        requires_auth = config.get('requires_auth', False)
        requires_headless = config.get('requires_headless', False)

        # Для hard paywall по умолчанию нужен headless
        if paywall_type == PaywallType.HARD:
            requires_headless = True
            requires_auth = True

        # Для freemium может требоваться проверка платформы
        platform = config.get('platform')

        return PaywallInfo(
            url=url,
            domain=domain,
            paywall_type=paywall_type,
            suggested_method=suggested_method,
            platform=platform,
            requires_auth=requires_auth,
            requires_headless=requires_headless,
            confidence=1.0,  # для конфига всегда полная уверенность
        )

    def reload(self) -> None:
        """Перезагрузить конфигурацию (без перезапуска бота)."""
        self._load_config()

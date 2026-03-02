"""Тесты для классификатора paywall."""

from pathlib import Path

import pytest
import yaml

from bot.constants import BypassMethod, PaywallType
from bot.services.paywall_classifier import PaywallClassifier


@pytest.fixture
def temp_config(tmp_path: Path) -> Path:
    """Создать временный YAML-конфиг для тестов."""
    config_data = {
        'spiegel.de': {
            'type': 'freemium',
            'platform': 'german_freemium',
            'method': 'js_disable',
        },
        'nytimes.com': {
            'type': 'metered',
            'method': 'googlebot_spoof',
        },
        'thetimes.com': {
            'type': 'hard',
            'method': 'headless_auth',
        },
    }

    config_file = tmp_path / 'paywall_map.yaml'
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f)

    return config_file


@pytest.mark.asyncio
async def test_classify_known_domain(temp_config: Path) -> None:
    """Классификация известного домена."""
    classifier = PaywallClassifier(temp_config)

    result = await classifier.classify('https://www.spiegel.de/artikel')

    assert result.domain == 'spiegel.de'
    assert result.paywall_type == PaywallType.FREEMIUM
    assert result.suggested_method == BypassMethod.JS_DISABLE
    assert result.platform == 'german_freemium'
    assert result.is_known is True
    assert result.can_bypass is True


@pytest.mark.asyncio
async def test_classify_hard_paywall(temp_config: Path) -> None:
    """Hard paywall должен выставлять requires_auth и requires_headless."""
    classifier = PaywallClassifier(temp_config)

    result = await classifier.classify('https://www.thetimes.com/article')

    assert result.paywall_type == PaywallType.HARD
    assert result.requires_auth is True
    assert result.requires_headless is True


@pytest.mark.asyncio
async def test_classify_unknown_domain(temp_config: Path) -> None:
    """Неизвестный домен возвращает UNKNOWN."""
    classifier = PaywallClassifier(temp_config)

    result = await classifier.classify('https://unknown-site.com')

    assert result.paywall_type == PaywallType.UNKNOWN
    assert result.suggested_method is None
    assert result.is_known is False
    assert result.can_bypass is False


@pytest.mark.asyncio
async def test_classify_subdomain_match(temp_config: Path) -> None:
    """Поддомен должен маппиться на основной домен."""
    classifier = PaywallClassifier(temp_config)

    result = await classifier.classify('https://news.spiegel.de/artikel')

    assert result.domain == 'news.spiegel.de'  # исходный домен сохраняется
    assert result.paywall_type == PaywallType.FREEMIUM  # но тип из spiegel.de


def test_config_not_found() -> None:
    """Ошибка при отсутствии файла конфига."""
    with pytest.raises(FileNotFoundError):
        PaywallClassifier(Path('/не/существует.yaml'))


@pytest.mark.asyncio
async def test_reload_config(temp_config: Path) -> None:
    """Перезагрузка конфига без перезапуска."""
    classifier = PaywallClassifier(temp_config)

    # Сначала неизвестный домен
    result1 = await classifier.classify('https://ft.com')
    assert result1.paywall_type == PaywallType.UNKNOWN

    # Добавляем новый домен в конфиг
    with open(temp_config, 'a', encoding='utf-8') as f:
        f.write('\nft.com:\n  type: metered\n  method: googlebot_spoof\n')

    # Перезагружаем
    classifier.reload()

    # Теперь домен известен
    result2 = await classifier.classify('https://ft.com')
    assert result2.paywall_type == PaywallType.METERED

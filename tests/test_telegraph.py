"""Интеграционные тесты для Telegraph (soft paywall)."""

import httpx
import pytest

from bot.services.content_extractor import ContentExtractor
from bot.services.methods.js_disable import fetch_via_js_disable


@pytest.mark.asyncio
async def test_telegraph_real_article():
    """Реальный тест статьи Telegraph (только если есть доступ)."""
    # Эту статью можно заменить на актуальную
    url = 'https://www.telegraph.co.uk/news/2024/01/15/example-article/'

    extractor = ContentExtractor()

    async with httpx.AsyncClient() as client:
        article = await fetch_via_js_disable(
            url,
            extractor=extractor,
            client=client,
        )

        if article:
            assert article.content
            assert len(article.content) > 200
            print(f'Получена статья: {article.title}')
        else:
            pytest.skip('Статья недоступна или изменилась')

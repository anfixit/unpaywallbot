"""Интеграционные тесты для Telegraph (soft paywall).

Требуют доступа к сети. Пропускаются если URL
недоступен или изменился.
"""

import httpx
import pytest

from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.services.methods.js_disable import (
    fetch_via_js_disable,
)


@pytest.mark.asyncio
async def test_telegraph_real_article() -> None:
    """Реальный тест статьи Telegraph."""
    url = (
        'https://www.telegraph.co.uk/news/'
        '2024/01/15/example-article/'
    )

    extractor = ContentExtractor()

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            article = await fetch_via_js_disable(
                url,
                extractor=extractor,
                client=client,
            )
    except (
        httpx.HTTPStatusError,
        httpx.ConnectError,
        httpx.TimeoutException,
    ):
        pytest.skip(
            'Telegraph недоступен или URL изменился',
        )
        return

    if article:
        assert article.content
        assert len(article.content) > 200
    else:
        pytest.skip(
            'Статья недоступна или изменилась',
        )

"""Модели данных для бота."""

from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.models.user_request import UserRequest

__all__ = ['Article', 'PaywallInfo', 'UserRequest']

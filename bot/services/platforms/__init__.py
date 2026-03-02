"""Платформенные обработчики."""

from bot.services.platforms.conde_nast import CondeNastPlatform
from bot.services.platforms.german_freemium import GermanFreemiumPlatform
from bot.services.platforms.republic import RepublicPlatform

__all__ = ['GermanFreemiumPlatform', 'CondeNastPlatform', 'RepublicPlatform']

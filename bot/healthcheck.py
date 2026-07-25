"""Container healthcheck for Redis connectivity."""

import asyncio
import sys

from redis.asyncio import Redis

from bot.config import settings


async def check() -> bool:
    """Return True when Redis accepts commands."""
    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        return bool(await client.ping())
    finally:
        await client.aclose()


def main() -> int:
    """Run healthcheck and return a shell exit code."""
    try:
        healthy = asyncio.run(check())
    except Exception:
        return 1
    return 0 if healthy else 1


if __name__ == '__main__':
    sys.exit(main())

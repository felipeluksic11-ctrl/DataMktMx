"""Dramatiq broker configuration.

Must be imported before any @dramatiq.actor decorators are evaluated.
Configures the Redis broker using settings (redis_host, redis_port, etc.)
instead of Dramatiq's default localhost:6379.
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from shared.config import settings

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)

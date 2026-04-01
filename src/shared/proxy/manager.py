"""Multi-provider proxy management with rotation, sessions, and health tracking.

Supports:
- DataImpulse (residential) — primary, charged per GB
- BrightData (residential/datacenter) — secondary, charged per IP+GB
- Custom SOCKS5/HTTP proxies

Each worker gets a unique proxy session to avoid correlation.
"""

import random
import time
from dataclasses import dataclass, field
from enum import StrEnum

from shared.logging import get_logger

logger = get_logger("proxy.manager")


class ProxyProvider(StrEnum):
    DATAIMPLULSE = "dataimplulse"
    BRIGHTDATA = "brightdata"
    CUSTOM = "custom"
    DIRECT = "direct"


class ProxyType(StrEnum):
    RESIDENTIAL = "residential"
    DATACENTER = "datacenter"
    MOBILE = "mobile"


@dataclass
class ProxyConfig:
    """Configuration for a single proxy provider."""
    provider: ProxyProvider
    proxy_type: ProxyType
    url_template: str  # URL with {session} placeholder for sticky sessions
    country: str = "mx"  # target country code
    enabled: bool = True
    max_concurrent: int = 10
    avg_cost_per_gb: float = 0.0  # USD

    def build_url(self, session_id: str = "") -> str:
        """Build a proxy URL with a unique session ID for sticky sessions."""
        return self.url_template.replace("{session}", session_id)


@dataclass
class ProxyHealth:
    """Tracks health of a proxy session."""
    session_id: str
    provider: ProxyProvider
    requests_made: int = 0
    requests_failed: int = 0
    bytes_transferred: int = 0
    last_used: float = 0.0
    last_error: str | None = None
    is_blocked: bool = False

    @property
    def failure_rate(self) -> float:
        if self.requests_made == 0:
            return 0.0
        return self.requests_failed / self.requests_made

    @property
    def is_healthy(self) -> bool:
        return not self.is_blocked and self.failure_rate < 0.3


@dataclass
class ProxySession:
    """A unique proxy session assigned to a worker."""
    session_id: str
    provider: ProxyProvider
    proxy_url: str
    country: str
    health: ProxyHealth


class ProxyManager:
    """Manages proxy sessions across multiple providers.

    Usage:
        manager = ProxyManager(configs=[...])
        session = manager.create_session(worker_id="worker-cdmx-1")
        proxy_url = session.proxy_url  # use in browser
        manager.report_success(session)  # after successful request
        manager.report_failure(session, "403 blocked")  # after failure
    """

    def __init__(self, configs: list[ProxyConfig] | None = None):
        self._configs: dict[ProxyProvider, ProxyConfig] = {}
        self._sessions: dict[str, ProxySession] = {}
        self._health: dict[str, ProxyHealth] = {}

        if configs:
            for cfg in configs:
                if cfg.enabled:
                    self._configs[cfg.provider] = cfg

    @classmethod
    def from_settings(cls) -> "ProxyManager":
        """Create ProxyManager from application settings."""
        from shared.config.settings import settings

        configs = []

        if settings.proxy_dataimplulse_url:
            configs.append(ProxyConfig(
                provider=ProxyProvider.DATAIMPLULSE,
                proxy_type=ProxyType.RESIDENTIAL,
                url_template=settings.proxy_dataimplulse_url,
                country="mx",
                avg_cost_per_gb=1.5,
            ))

        if settings.proxy_brightdata_url:
            configs.append(ProxyConfig(
                provider=ProxyProvider.BRIGHTDATA,
                proxy_type=ProxyType.RESIDENTIAL,
                url_template=settings.proxy_brightdata_url,
                country="mx",
                avg_cost_per_gb=3.0,
            ))

        return cls(configs=configs)

    def create_session(
        self,
        worker_id: str,
        provider: ProxyProvider | None = None,
        country: str = "mx",
    ) -> ProxySession:
        """Create a unique proxy session for a worker.

        Each worker gets its own session ID to ensure different IPs
        and prevent correlation between workers.
        """
        # Select provider
        if provider and provider != ProxyProvider.DIRECT:
            cfg = self._configs.get(provider)
        else:
            cfg = self._pick_best_provider()

        if not cfg:
            # No proxy available — return direct connection
            session = ProxySession(
                session_id=f"direct-{worker_id}",
                provider=ProxyProvider.DIRECT,
                proxy_url="",
                country=country,
                health=ProxyHealth(
                    session_id=f"direct-{worker_id}",
                    provider=ProxyProvider.DIRECT,
                ),
            )
            self._sessions[session.session_id] = session
            logger.warning("proxy.no_provider_available", worker=worker_id)
            return session

        # Generate unique session ID
        session_id = f"{worker_id}-{cfg.provider}-{random.randint(100000, 999999)}"
        proxy_url = cfg.build_url(session_id)

        health = ProxyHealth(session_id=session_id, provider=cfg.provider)
        session = ProxySession(
            session_id=session_id,
            provider=cfg.provider,
            proxy_url=proxy_url,
            country=country,
            health=health,
        )

        self._sessions[session_id] = session
        self._health[session_id] = health

        logger.info(
            "proxy.session_created",
            worker=worker_id,
            provider=str(cfg.provider),
            session=session_id,
            country=country,
        )
        return session

    def rotate_session(self, old_session: ProxySession, worker_id: str) -> ProxySession:
        """Create a new session for a worker, replacing a blocked/unhealthy one."""
        old_session.health.is_blocked = True
        logger.warning(
            "proxy.rotating",
            old_session=old_session.session_id,
            failure_rate=old_session.health.failure_rate,
        )

        # Try a different provider if available
        other_providers = [p for p in self._configs if p != old_session.provider]
        provider = random.choice(other_providers) if other_providers else None

        return self.create_session(worker_id, provider=provider, country=old_session.country)

    def report_success(self, session: ProxySession, bytes_count: int = 0) -> None:
        """Report a successful request through this proxy session."""
        session.health.requests_made += 1
        session.health.bytes_transferred += bytes_count
        session.health.last_used = time.time()

    def report_failure(self, session: ProxySession, error: str = "") -> None:
        """Report a failed request. Auto-marks as blocked if failure rate too high."""
        session.health.requests_made += 1
        session.health.requests_failed += 1
        session.health.last_error = error
        session.health.last_used = time.time()

        if session.health.failure_rate > 0.3 and session.health.requests_made >= 5:
            session.health.is_blocked = True
            logger.warning(
                "proxy.session_blocked",
                session=session.session_id,
                failure_rate=session.health.failure_rate,
            )

    def get_stats(self) -> dict:
        """Get aggregate stats across all sessions."""
        total_requests = sum(h.requests_made for h in self._health.values())
        total_failed = sum(h.requests_failed for h in self._health.values())
        total_bytes = sum(h.bytes_transferred for h in self._health.values())
        active = sum(1 for s in self._sessions.values() if s.health.is_healthy)
        blocked = sum(1 for s in self._sessions.values() if s.health.is_blocked)

        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active,
            "blocked_sessions": blocked,
            "total_requests": total_requests,
            "total_failed": total_failed,
            "failure_rate": total_failed / total_requests if total_requests > 0 else 0,
            "total_bytes_gb": round(total_bytes / (1024**3), 3),
            "providers": {
                str(p): {
                    "enabled": c.enabled,
                    "type": str(c.proxy_type),
                    "cost_per_gb": c.avg_cost_per_gb,
                }
                for p, c in self._configs.items()
            },
        }

    def _pick_best_provider(self) -> ProxyConfig | None:
        """Pick the best available provider based on health and cost."""
        available = [c for c in self._configs.values() if c.enabled]
        if not available:
            return None

        # Prefer residential over datacenter
        residential = [c for c in available if c.proxy_type == ProxyType.RESIDENTIAL]
        if residential:
            # Pick cheapest residential
            return min(residential, key=lambda c: c.avg_cost_per_gb)

        return available[0]

    @property
    def has_proxies(self) -> bool:
        return len(self._configs) > 0

    @property
    def available_providers(self) -> list[ProxyProvider]:
        return list(self._configs.keys())

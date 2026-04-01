"""Worker identity system — generates unique, non-correlatable browser profiles.

Each worker gets:
- Unique proxy session (different IP)
- Unique browser fingerprint (Camoufox handles most)
- Unique viewport, timezone, locale
- Unique delay pattern (gaussian distribution with different mean/std)
- Unique navigation order (shuffled states/pages)

The goal: N workers look like N unrelated real users.
"""

import random
from dataclasses import dataclass, field

from shared.logging import get_logger

logger = get_logger("stealth.identity")

# Realistic viewport sizes from common devices
VIEWPORTS = [
    (1920, 1080),  # Full HD
    (1366, 768),   # Laptop common
    (1536, 864),   # Laptop HD+
    (1440, 900),   # MacBook
    (1280, 720),   # HD
    (2560, 1440),  # QHD
    (1600, 900),   # Laptop wide
    (1280, 800),   # MacBook older
    (1680, 1050),  # WSXGA+
    (1920, 1200),  # WUXGA
]

# Mexican timezones
TIMEZONES = [
    "America/Mexico_City",
    "America/Monterrey",
    "America/Merida",
    "America/Cancun",
    "America/Chihuahua",
    "America/Mazatlan",
    "America/Hermosillo",
    "America/Tijuana",
]

# Mexican locales
LOCALES = [
    "es-MX",
    "es-419",
    "es",
]

# Realistic delay profiles (mean_ms, std_ms)
DELAY_PROFILES = [
    (2500, 800),   # Fast but careful user
    (3500, 1200),  # Average user
    (4500, 1500),  # Slow careful user
    (3000, 1000),  # Moderate
    (5000, 2000),  # Very slow, cautious
    (2000, 600),   # Quick browser
    (4000, 1300),  # Methodical
]


@dataclass
class WorkerIdentity:
    """Unique identity for a scraping worker — makes it look like a distinct real user."""

    worker_id: str
    viewport_width: int
    viewport_height: int
    timezone: str
    locale: str
    delay_mean_ms: float
    delay_std_ms: float
    headless: bool = True
    navigation_timeout_ms: int = 60_000
    page_timeout_ms: int = 30_000

    def random_delay(self) -> float:
        """Generate a random delay in seconds following this worker's unique pattern."""
        delay_ms = max(500, random.gauss(self.delay_mean_ms, self.delay_std_ms))
        return delay_ms / 1000.0

    def random_long_delay(self) -> float:
        """Longer delay for between pages (simulates reading/scrolling)."""
        return self.random_delay() * random.uniform(1.5, 3.0)


def create_identity(worker_id: str, seed: int | None = None) -> WorkerIdentity:
    """Create a unique, deterministic identity for a worker.

    Same worker_id + seed always produces the same identity,
    so restarts don't change the fingerprint mid-session.
    """
    rng = random.Random(f"{worker_id}-{seed or 0}")

    viewport = rng.choice(VIEWPORTS)
    timezone = rng.choice(TIMEZONES)
    locale = rng.choice(LOCALES)
    delay_profile = rng.choice(DELAY_PROFILES)

    identity = WorkerIdentity(
        worker_id=worker_id,
        viewport_width=viewport[0],
        viewport_height=viewport[1],
        timezone=timezone,
        locale=locale,
        delay_mean_ms=delay_profile[0],
        delay_std_ms=delay_profile[1],
    )

    logger.info(
        "identity.created",
        worker=worker_id,
        viewport=f"{viewport[0]}x{viewport[1]}",
        timezone=timezone,
        locale=locale,
        delay_mean=delay_profile[0],
    )

    return identity

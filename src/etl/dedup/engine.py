"""Cross-portal deduplication engine.

Strategy: deterministic rules first, fuzzy matching second.

Two listings are duplicates if:
1. EXACT match: same normalized address + same price ± 5% + same property type
2. NEAR match: fuzzy address similarity > 85% + same price ± 10% + same area ± 15%

We group duplicates into clusters. The "best" listing in each cluster
(highest completeness) becomes the canonical one; others link to it.

Uses thefuzz for string similarity — fast enough for 100K-1M listings
when pre-filtered by state + municipality + price range.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from thefuzz import fuzz

from shared.logging import get_logger

logger = get_logger("etl.dedup")


@dataclass
class ListingForDedup:
    """Minimal listing representation for dedup comparison."""
    id: str
    portal_slug: str
    state_code: str | None = None
    municipality: str | None = None
    neighborhood: str | None = None
    price_mxn: float | None = None
    property_type: str | None = None
    construction_m2: float | None = None
    land_m2: float | None = None
    bedrooms: int | None = None
    street: str | None = None
    completeness: float = 0.0


@dataclass
class DedupCluster:
    """A group of listings that represent the same physical property."""
    cluster_id: str = field(default_factory=lambda: str(uuid4()))
    listings: list[ListingForDedup] = field(default_factory=list)
    canonical_id: str | None = None  # the "best" listing in the cluster

    @property
    def source_count(self) -> int:
        return len({l.portal_slug for l in self.listings})

    def pick_canonical(self) -> str:
        """Pick the listing with highest completeness as canonical."""
        best = max(self.listings, key=lambda l: l.completeness)
        self.canonical_id = best.id
        return best.id


def _price_similar(a: float | None, b: float | None, tolerance: float = 0.05) -> bool:
    """Check if two prices are within tolerance of each other."""
    if a is None or b is None:
        return False
    if a == 0 or b == 0:
        return False
    ratio = min(a, b) / max(a, b)
    return ratio >= (1.0 - tolerance)


def _area_similar(a: float | None, b: float | None, tolerance: float = 0.15) -> bool:
    """Check if two areas are within tolerance."""
    if a is None or b is None:
        return True  # don't penalize missing area
    if a == 0 or b == 0:
        return True
    ratio = min(a, b) / max(a, b)
    return ratio >= (1.0 - tolerance)


def _address_similar(a: str | None, b: str | None, threshold: int = 85) -> bool:
    """Fuzzy string match on addresses."""
    if not a or not b:
        return False
    score = fuzz.token_sort_ratio(a.lower(), b.lower())
    return score >= threshold


def find_duplicates(listings: list[ListingForDedup]) -> list[DedupCluster]:
    """Find duplicate clusters across all listings.

    Pre-filters by state + municipality to reduce comparison space.
    Within each group, compares price + area + address.
    """
    # Group by (state, municipality, property_type) to reduce comparisons
    groups: dict[tuple, list[ListingForDedup]] = {}
    for listing in listings:
        key = (
            listing.state_code or "",
            (listing.municipality or "").lower(),
            listing.property_type or "",
        )
        groups.setdefault(key, []).append(listing)

    clusters: list[DedupCluster] = []
    assigned: set[str] = set()  # listing IDs already in a cluster

    for group_key, group_listings in groups.items():
        if len(group_listings) < 2:
            continue

        for i, a in enumerate(group_listings):
            if a.id in assigned:
                continue

            cluster = DedupCluster()
            cluster.listings.append(a)
            assigned.add(a.id)

            for b in group_listings[i + 1:]:
                if b.id in assigned:
                    continue

                # Same portal → not a cross-portal duplicate
                if a.portal_slug == b.portal_slug:
                    continue

                # Price must be similar
                if not _price_similar(a.price_mxn, b.price_mxn, tolerance=0.10):
                    continue

                # Area must be similar (if both have it)
                area_a = a.construction_m2 or a.land_m2
                area_b = b.construction_m2 or b.land_m2
                if not _area_similar(area_a, area_b, tolerance=0.15):
                    continue

                # Bedrooms must match (if both have it)
                if a.bedrooms and b.bedrooms and a.bedrooms != b.bedrooms:
                    continue

                # Address or neighborhood similarity
                addr_match = False
                if a.street and b.street:
                    addr_match = _address_similar(a.street, b.street, threshold=80)
                elif a.neighborhood and b.neighborhood:
                    addr_match = _address_similar(a.neighborhood, b.neighborhood, threshold=85)

                if addr_match:
                    cluster.listings.append(b)
                    assigned.add(b.id)

            if len(cluster.listings) > 1:
                cluster.pick_canonical()
                clusters.append(cluster)

    logger.info(
        "dedup.completed",
        total_listings=len(listings),
        clusters_found=len(clusters),
        duplicates=sum(len(c.listings) - 1 for c in clusters),
    )

    return clusters

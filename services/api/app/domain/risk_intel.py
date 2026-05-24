from __future__ import annotations

from datetime import UTC, datetime

from app.connectors.goplus import GoPlusClient
from app.domain.models import (
    DIRECT_HIT_CATEGORIES,
    RiskLevel,
    RiskSourceHit,
    WatchlistEntry,
)
from app.domain.providers import (
    SOURCE_GOPLUS,
    GoPlusRiskProvider,
    RiskProvider,
    _goplus_behaviors,
    _goplus_doubt_list,
)


SEVERITY_WEIGHTS = {
    RiskLevel.low: 10,
    RiskLevel.medium: 35,
    RiskLevel.high: 70,
    RiskLevel.critical: 95,
}

# Canonical source names used in SourceHit.source
SOURCE_WATCHLIST = "local_watchlist"


PUBLIC_DEMO_TAGS: dict[str, WatchlistEntry] = {}


class RiskIntelAggregator:
    """Aggregates risk signals from GoPlus, local watchlist, and pattern analysis.

    Every ``SourceHit`` produced by this aggregator carries:
    - ``source``: canonical source identifier (goplus, local_watchlist, ofac, etc.)
    - ``category``: risk category (ofac, pep, sanctions, stablecoin_blacklist, …)
    - ``severity``: RiskLevel enum
    - ``confidence``: 0–1 float
    - ``direct_hit``: True when category is in ``DIRECT_HIT_CATEGORIES``
    - ``source_updated_at``: timestamp of the hit (``seen_at`` semantics)
    """

    def __init__(self, goplus: GoPlusClient, providers: list[RiskProvider] | None = None) -> None:
        self.providers = providers if providers is not None else [GoPlusRiskProvider(goplus)]

    async def enrich_address(
        self,
        address: str,
        chain_id: str,
        local_watchlist: dict[str, WatchlistEntry],
    ) -> tuple[list[str], list[tuple[str, RiskLevel, str]]]:
        tags, findings, _source_hits = await self.enrich_address_detail(address, chain_id, local_watchlist)
        return tags, findings

    async def enrich_address_detail(
        self,
        address: str,
        chain_id: str,
        local_watchlist: dict[str, WatchlistEntry],
    ) -> tuple[list[str], list[tuple[str, RiskLevel, str]], list[RiskSourceHit]]:
        tags: list[str] = []
        findings: list[tuple[str, RiskLevel, str]] = []
        source_hits: list[RiskSourceHit] = []
        normalized = address.lower()
        now = datetime.now(UTC)

        # ── Watchlist / demo tags ──────────────────────────────────────────
        watchlist_entry = local_watchlist.get(normalized) or PUBLIC_DEMO_TAGS.get(normalized)
        if watchlist_entry:
            tags.append(watchlist_entry.label)
            category = watchlist_entry.category.lower()
            evidence = watchlist_entry.evidence or watchlist_entry.notes or f"Watchlist hit: {watchlist_entry.label}"
            findings.append((watchlist_entry.category, watchlist_entry.severity, evidence))
            is_direct = category in DIRECT_HIT_CATEGORIES
            # Map category to canonical source name for the hit
            source_name = _source_for_watchlist_entry(watchlist_entry, category)
            source_hits.append(
                RiskSourceHit(
                    source=source_name,
                    category=watchlist_entry.category,
                    severity=watchlist_entry.severity,
                    address=normalized,
                    label=watchlist_entry.label,
                    evidence=evidence,
                    confidence=1.0,
                    source_updated_at=now,
                    direct_hit=is_direct or watchlist_entry.severity == RiskLevel.critical,
                    raw_payload=watchlist_entry.model_dump(),
                )
            )

        # ── Provider API results ──────────────────────────────────────────
        for provider in self.providers:
            result = await provider.check_address(normalized, chain_id=chain_id, seen_at=now)
            tags.extend(result.tags)
            findings.extend(result.findings)
            source_hits.extend(result.source_hits)

        deduped_tags = sorted(set(tags))
        return deduped_tags, findings, source_hits


def _source_for_category(category: str) -> str:
    """Return canonical source name for a watchlist category.

    Categories that match known external lists get their own source name so
    downstream consumers can distinguish the authoritative source.
    """
    mapping = {
        "ofac": "ofac",
        "sanctions": "sanctions",
        "sanctioned": "sanctions",
        "pep": "pep",
        "circle_blacklist": "circle_blacklist",
        "tether_blacklist": "tether_blacklist",
        "stablecoin_blacklist": "stablecoin_blacklist",
    }
    return mapping.get(category.lower(), SOURCE_WATCHLIST)


def _source_for_watchlist_entry(entry: WatchlistEntry, category: str) -> str:
    source = entry.source.strip()
    if source and source not in {"manual", "manual_import", SOURCE_WATCHLIST}:
        return source
    return _source_for_category(category)


from __future__ import annotations

from datetime import UTC, datetime

from app.connectors.goplus import HIGH_RISK_BEHAVIORS, GoPlusClient
from app.domain.models import (
    DIRECT_HIT_CATEGORIES,
    RiskLevel,
    RiskSourceHit,
    WatchlistEntry,
)


SEVERITY_WEIGHTS = {
    RiskLevel.low: 10,
    RiskLevel.medium: 35,
    RiskLevel.high: 70,
    RiskLevel.critical: 95,
}

# Canonical source names used in SourceHit.source
SOURCE_GOPLUS = "goplus"
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

    def __init__(self, goplus: GoPlusClient) -> None:
        self.goplus = goplus

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
            findings.append((watchlist_entry.category, watchlist_entry.severity, watchlist_entry.notes))
            category = watchlist_entry.category.lower()
            is_direct = category in DIRECT_HIT_CATEGORIES
            # Map category to canonical source name for the hit
            source_name = _source_for_category(category)
            source_hits.append(
                RiskSourceHit(
                    source=source_name,
                    category=watchlist_entry.category,
                    severity=watchlist_entry.severity,
                    address=normalized,
                    label=watchlist_entry.label,
                    evidence=watchlist_entry.notes or f"Watchlist hit: {watchlist_entry.label}",
                    confidence=1.0,
                    source_updated_at=now,
                    direct_hit=is_direct or watchlist_entry.severity == RiskLevel.critical,
                    raw_payload=watchlist_entry.model_dump(),
                )
            )

        # ── GoPlus API ────────────────────────────────────────────────────
        goplus_result = await self.goplus.get_address_security(normalized, chain_id=chain_id)
        behaviors = goplus_result.get("malicious_behavior") or []
        if isinstance(behaviors, str):
            behaviors = [behaviors]
        for behavior in behaviors:
            if not behavior:
                continue
            behavior_str = str(behavior)
            tags.append(behavior_str)
            severity = RiskLevel.critical if behavior in HIGH_RISK_BEHAVIORS else RiskLevel.high
            findings.append(("goplus", severity, f"GoPlus malicious behavior: {behavior_str}"))
            category_lower = behavior_str.lower()
            source_hits.append(
                RiskSourceHit(
                    source=SOURCE_GOPLUS,
                    category=behavior_str,
                    severity=severity,
                    address=normalized,
                    label=behavior_str,
                    evidence=f"GoPlus malicious behavior: {behavior_str}",
                    confidence=0.90,
                    source_updated_at=now,
                    direct_hit=category_lower in DIRECT_HIT_CATEGORIES,
                    raw_payload=goplus_result,
                )
            )

        if goplus_result.get("doubt_list") == "1" and not behaviors:
            tags.append("doubt_list")
            findings.append(("goplus", RiskLevel.medium, "GoPlus marks the address as suspicious."))
            source_hits.append(
                RiskSourceHit(
                    source=SOURCE_GOPLUS,
                    category="doubt_list",
                    severity=RiskLevel.medium,
                    address=normalized,
                    label="doubt_list",
                    evidence="GoPlus marks the address as suspicious.",
                    confidence=0.65,
                    source_updated_at=now,
                    raw_payload=goplus_result,
                )
            )
        if goplus_result.get("trust_list") == "1":
            tags.append("trust_list")

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

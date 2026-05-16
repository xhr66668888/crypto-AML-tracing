from __future__ import annotations

from app.connectors.goplus import HIGH_RISK_BEHAVIORS, GoPlusClient
from app.domain.models import RiskLevel, RiskSourceHit, WatchlistEntry


SEVERITY_WEIGHTS = {
    RiskLevel.low: 10,
    RiskLevel.medium: 35,
    RiskLevel.high: 70,
    RiskLevel.critical: 95,
}


PUBLIC_DEMO_TAGS: dict[str, WatchlistEntry] = {}

DIRECT_HIT_CATEGORIES = {
    "ofac",
    "sanctions",
    "sanctioned",
    "pep",
    "circle_blacklist",
    "tether_blacklist",
    "stablecoin_blacklist",
}


class RiskIntelAggregator:
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

        watchlist_entry = local_watchlist.get(normalized) or PUBLIC_DEMO_TAGS.get(normalized)
        if watchlist_entry:
            tags.append(watchlist_entry.label)
            findings.append((watchlist_entry.category, watchlist_entry.severity, watchlist_entry.notes))
            category = watchlist_entry.category.lower()
            source_hits.append(
                RiskSourceHit(
                    source="local_watchlist",
                    category=watchlist_entry.category,
                    severity=watchlist_entry.severity,
                    address=normalized,
                    label=watchlist_entry.label,
                    evidence=watchlist_entry.notes or f"Local watchlist hit: {watchlist_entry.label}",
                    direct_hit=category in DIRECT_HIT_CATEGORIES or watchlist_entry.severity == RiskLevel.critical,
                    raw_payload=watchlist_entry.model_dump(),
                )
            )

        goplus_result = await self.goplus.get_address_security(normalized, chain_id=chain_id)
        behaviors = goplus_result.get("malicious_behavior") or []
        if isinstance(behaviors, str):
            behaviors = [behaviors]
        for behavior in behaviors:
            if not behavior:
                continue
            tags.append(str(behavior))
            severity = RiskLevel.critical if behavior in HIGH_RISK_BEHAVIORS else RiskLevel.high
            findings.append(("goplus", severity, f"GoPlus malicious behavior: {behavior}"))
            source_hits.append(
                RiskSourceHit(
                    source="goplus",
                    category=str(behavior),
                    severity=severity,
                    address=normalized,
                    label=str(behavior),
                    evidence=f"GoPlus malicious behavior: {behavior}",
                    direct_hit=str(behavior).lower() in DIRECT_HIT_CATEGORIES,
                    raw_payload=goplus_result,
                )
            )

        if goplus_result.get("doubt_list") == "1" and not behaviors:
            tags.append("doubt_list")
            findings.append(("goplus", RiskLevel.medium, "GoPlus marks the address as suspicious."))
            source_hits.append(
                RiskSourceHit(
                    source="goplus",
                    category="doubt_list",
                    severity=RiskLevel.medium,
                    address=normalized,
                    label="doubt_list",
                    evidence="GoPlus marks the address as suspicious.",
                    confidence=0.65,
                    raw_payload=goplus_result,
                )
            )
        if goplus_result.get("trust_list") == "1":
            tags.append("trust_list")

        deduped_tags = sorted(set(tags))
        return deduped_tags, findings, source_hits

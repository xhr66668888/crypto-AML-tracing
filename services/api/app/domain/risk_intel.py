from __future__ import annotations

from app.connectors.goplus import HIGH_RISK_BEHAVIORS, GoPlusClient
from app.domain.models import RiskLevel, WatchlistEntry


SEVERITY_WEIGHTS = {
    RiskLevel.low: 10,
    RiskLevel.medium: 35,
    RiskLevel.high: 70,
    RiskLevel.critical: 95,
}


PUBLIC_DEMO_TAGS: dict[str, WatchlistEntry] = {}


class RiskIntelAggregator:
    def __init__(self, goplus: GoPlusClient) -> None:
        self.goplus = goplus

    async def enrich_address(
        self,
        address: str,
        chain_id: str,
        local_watchlist: dict[str, WatchlistEntry],
    ) -> tuple[list[str], list[tuple[str, RiskLevel, str]]]:
        tags: list[str] = []
        findings: list[tuple[str, RiskLevel, str]] = []
        normalized = address.lower()

        watchlist_entry = local_watchlist.get(normalized) or PUBLIC_DEMO_TAGS.get(normalized)
        if watchlist_entry:
            tags.append(watchlist_entry.label)
            findings.append((watchlist_entry.category, watchlist_entry.severity, watchlist_entry.notes))

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

        if goplus_result.get("doubt_list") == "1" and not behaviors:
            tags.append("doubt_list")
            findings.append(("goplus", RiskLevel.medium, "GoPlus marks the address as suspicious."))
        if goplus_result.get("trust_list") == "1":
            tags.append("trust_list")

        deduped_tags = sorted(set(tags))
        return deduped_tags, findings

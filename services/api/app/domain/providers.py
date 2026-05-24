from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.connectors.base import ConnectorError
from app.connectors.goplus import HIGH_RISK_BEHAVIORS, GoPlusClient
from app.domain.models import DIRECT_HIT_CATEGORIES, RiskLevel, RiskSourceHit


SOURCE_GOPLUS = "goplus"


@dataclass(frozen=True)
class RiskProviderResult:
    tags: list[str] = field(default_factory=list)
    findings: list[tuple[str, RiskLevel, str]] = field(default_factory=list)
    source_hits: list[RiskSourceHit] = field(default_factory=list)


class RiskProvider(Protocol):
    name: str
    risk_domain: str

    async def check_address(self, address: str, chain_id: str, seen_at: datetime) -> RiskProviderResult:
        ...


@dataclass
class GoPlusRiskProvider:
    goplus: GoPlusClient
    name: str = SOURCE_GOPLUS
    risk_domain: str = "web3_security"

    async def check_address(self, address: str, chain_id: str, seen_at: datetime) -> RiskProviderResult:
        try:
            goplus_result = await self.goplus.get_address_security(address, chain_id=chain_id)
        except ConnectorError as exc:
            if not exc.retryable:
                raise
            return RiskProviderResult(
                tags=[f"{self.name}_unavailable"],
                findings=[
                    (
                        "provider_unavailable",
                        RiskLevel.low,
                        f"GoPlus risk check unavailable for {address}: {exc.message}",
                    )
                ],
            )

        tags: list[str] = []
        findings: list[tuple[str, RiskLevel, str]] = []
        source_hits: list[RiskSourceHit] = []

        for behavior in _goplus_behaviors(goplus_result):
            behavior_str = str(behavior)
            tags.append(behavior_str)
            severity = RiskLevel.critical if behavior in HIGH_RISK_BEHAVIORS else RiskLevel.high
            evidence = f"GoPlus malicious behavior: {behavior_str}"
            findings.append((self.name, severity, evidence))
            category_lower = behavior_str.lower()
            source_hits.append(
                RiskSourceHit(
                    source=self.name,
                    category=behavior_str,
                    severity=severity,
                    address=address,
                    label=behavior_str,
                    evidence=evidence,
                    confidence=0.90,
                    source_updated_at=seen_at,
                    direct_hit=category_lower in DIRECT_HIT_CATEGORIES,
                    raw_payload=goplus_result,
                )
            )

        if _goplus_doubt_list(goplus_result) and not source_hits:
            tags.append("doubt_list")
            evidence = "GoPlus marks the address as suspicious."
            findings.append((self.name, RiskLevel.medium, evidence))
            source_hits.append(
                RiskSourceHit(
                    source=self.name,
                    category="doubt_list",
                    severity=RiskLevel.medium,
                    address=address,
                    label="doubt_list",
                    evidence=evidence,
                    confidence=0.65,
                    source_updated_at=seen_at,
                    raw_payload=goplus_result,
                )
            )
        if goplus_result.get("trust_list") == "1":
            tags.append("trust_list")

        return RiskProviderResult(tags=tags, findings=findings, source_hits=source_hits)


def _goplus_behaviors(result: dict) -> list[str]:
    behaviors = result.get("malicious_behavior") or []
    if isinstance(behaviors, str):
        behaviors = [behaviors]
    extracted = [str(behavior) for behavior in behaviors if behavior]
    for behavior in HIGH_RISK_BEHAVIORS:
        if _is_enabled(result.get(behavior)):
            extracted.append(behavior)
    return sorted(set(extracted))


def _goplus_doubt_list(result: dict) -> bool:
    return _is_enabled(result.get("doubt_list")) or _is_enabled(result.get("blacklist_doubt"))


def _is_enabled(value) -> bool:
    return value is True or str(value).strip() == "1"

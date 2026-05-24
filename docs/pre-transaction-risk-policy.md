# Pre-Transaction Risk Policy

This policy defines the MVP business decision rules for proposed inbound and
outbound Ethereum transactions. It is a product policy layer: scoring measures
risk intensity, while disposition decides whether funds can move now.

## Product Boundary

The MVP answers one operational question:

> Can this proposed transaction be allowed now? If not, what evidence supports
> review or hold?

The scanner evaluates transaction context before funds are released or accepted.
It is not a complete post-transaction tracing product and must not claim full
fund provenance from bounded graph context.

## Direction Logic

Inbound screening evaluates funds a customer or counterparty wants to send into
Cregis-controlled custody.

- The primary counterparty is `from_address`.
- A direct hit on `from_address` forces the configured direct-hit disposition.
- A direct hit on `to_address` still appears as evidence, but it is treated as
  internal exposure unless the address is not Cregis-controlled.
- Recent risky exposure from the sender supports review, not automatic hold,
  unless it is backed by a direct-hit source.

Outbound screening evaluates funds Cregis may release to an external address.

- The primary counterparty is `to_address`.
- A direct hit on `to_address` forces the configured direct-hit disposition.
- A direct hit on `from_address` is treated as internal account risk and should
  trigger review unless the account itself is blocked by policy.
- Amount and repeated-transfer patterns can raise the disposition to review.

## Default Dispositions

`allow` is returned when all of the following are true:

- No direct-hit source hit exists for the primary counterparty.
- No high-confidence provider illicit hit exists.
- No material pattern signal indicates threshold structuring, dusting, recent
  risky exposure, or repeated short-time transfers.
- The final risk score is below `35`.

`review` is returned when any of the following is true:

- Final risk score is `35` or above and below `85`.
- PEP policy is configured to review rather than hold.
- Provider evidence is medium confidence or unavailable.
- Behavioral patterns are present without a direct-hit source.
- Amount is near or above the asset review threshold.

`hold_for_manual_review` is returned when any of the following is true:

- A direct-hit category is `ofac`, `sanctions`, `sanctioned`,
  `circle_blacklist`, `tether_blacklist`, or `stablecoin_blacklist`.
- PEP policy is configured to hold.
- Final risk score is `85` or above.
- A high-confidence provider illicit hit is backed by source evidence.

The current implementation keeps `pep` in the direct-hit category set, so PEP
hits force `hold_for_manual_review` until a configurable policy layer changes
that behavior.

## Amount Thresholds

These thresholds are MVP defaults for review routing. They are not regulatory
limits and should be revisited with Cregis compliance operators.

| Asset | Review threshold | High amount threshold | Notes |
| --- | ---: | ---: | --- |
| ETH | 10 ETH | 50 ETH | Native ETH transfer value. |
| USDT | 10,000 USDT | 100,000 USDT | ERC-20 transfer amount after decimals. |
| USDC | 10,000 USDC | 100,000 USDC | ERC-20 transfer amount after decimals. |
| Other ERC-20 | 10,000 USD equivalent | 100,000 USD equivalent | Use token metadata and pricing when available; otherwise review manually. |

Amounts within 10% below a review threshold should be treated as supporting
evidence for threshold-structuring review, not as a direct hold by themselves.

## Demo Data and Compliance Boundaries

Demo data must never be described as real intelligence. Any demo-mode screening,
report, fixture, or UI display must clearly say it is demonstration data.

The product may recommend review, hold, escalation, or evidence gathering. It
must not claim that an address is criminal, that funds are illegal, or that a
person is sanctioned unless the statement is directly backed by a source hit
from an authoritative or clearly labeled provider source.

Every risk conclusion must be traceable to a `source_hit`, `pattern_signal`, or
evidence row.

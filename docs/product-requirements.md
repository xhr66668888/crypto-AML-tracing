# Cregis AML Product Requirements Document

## Product Positioning

Cregis AML is first a pre-transaction risk screening product for crypto
transaction compliance. Before funds are released or accepted, the product
evaluates the proposed transfer and returns a disposition, risk score, risk
level, source-backed evidence, and recommended actions.

The first milestone is a pre-transaction scanning MVP. Deep post-transaction
investigation, broader graph exploration, and interactive copilot workflows are
supporting capabilities, not the primary product surface for this milestone.

This PRD describes the intended product direction. It is the source of truth for
future product alignment work and may differ from the current MVP
implementation.

## 1. Pre-Transaction Scanning MVP

### 1.1 Transaction Context

The scanner evaluates transaction context, not only one address. The expected
input includes:

- Chain ID.
- Direction: inbound or outbound.
- From address and to address.
- Asset type: native or ERC-20.
- Token address when applicable.
- Asset symbol.
- Amount.
- Optional customer ID and transaction hash.

### 1.2 Business Decision Output

Every screening decision must return:

- Final risk score and risk level.
- Disposition: `allow`, `review`, or `hold_for_manual_review`.
- Source hits and pattern signals.
- Evidence summary.
- Recommended actions.

### 1.3 Direction-Specific Decision Logic

Inbound transfers primarily evaluate the sender, `from_address`, because funds
are entering Cregis-controlled custody. Outbound transfers primarily evaluate
the recipient, `to_address`, because funds may be released to that external
counterparty.

Direct-hit evidence on the primary counterparty takes priority over behavioral
scores. Direct-hit evidence on the non-primary side is still shown as evidence
and normally routes to review unless a policy explicitly blocks that address.

### 1.4 Default Risk Policy

The default MVP policy is defined in
[`docs/pre-transaction-risk-policy.md`](pre-transaction-risk-policy.md). In
summary:

- `allow`: no direct hit, no material provider or pattern evidence, and score
  below `35`.
- `review`: score from `35` to below `85`, provider unavailable, PEP review
  policy, medium provider evidence, behavioral patterns, or amount-threshold
  evidence.
- `hold_for_manual_review`: OFAC, sanctions, Circle blacklist, Tether
  blacklist, stablecoin blacklist, configured PEP hold, high-confidence
  provider illicit hit, or score `85` and above.

### 1.5 Amount Thresholds

Default review thresholds:

- ETH: review at `10 ETH`, high amount at `50 ETH`.
- USDT: review at `10,000 USDT`, high amount at `100,000 USDT`.
- USDC: review at `10,000 USDC`, high amount at `100,000 USDC`.
- Other ERC-20 assets: review at `10,000 USD equivalent`, high amount at
  `100,000 USD equivalent` when token metadata and pricing are available.

Amounts close to thresholds are supporting evidence for review, not standalone
proof of illicit activity.

### 1.6 Demo and Compliance Boundaries

Demo data must always be labeled as demonstration data and must never be
described as real intelligence. Risk conclusions must cite source hits, pattern
signals, or evidence rows. The product may recommend allow, review, hold, or
escalation, but it must not assert criminality without source-backed evidence.

## 2. Risk Pattern Analysis

### 2.1 Money Laundering Pattern Recognition

Identify whether fund flows align with specific money laundering schemes, such
as Layering, Aggregation (splitting then consolidating), or Peel Chains.

### 2.2 Address Behavioral Profiling

Analyze account lifecycle traits, transaction behavior, and address reuse
patterns, including:

- Large transfers from new or dormant addresses.
- Anomalous high-frequency transfers.
- Micro-transfer behavior.
- Sequential transfers near thresholds.
- Use of disposable addresses.

### 2.3 Network Pattern Analysis

Utilize address clustering and centrality analysis to identify core nodes and
potential risk propagation paths within the network.

### 2.4 Dusting Attack Monitoring

Monitor dusting attacks targeting recent transaction addresses. The system must
provide high-risk alerts when a user attempts to withdraw funds to such
addresses.

### 2.5 Comprehensive Blacklist Database

Maintain a real-time database synced with international AML standards,
including:

- OFAC lists.
- PEP lists.
- Sanctions lists.
- Circle blacklist APIs.
- Tether blacklist APIs.

Every inbound and outbound transaction must be verified against this database.

## 3. Risk Control Agent / Copilot

### 3.1 Foundational Knowledge

Provide all users with introductions to Cregis AML and basic risk-control
concepts.

### 3.2 Onboarding and Configuration

Guide new users through product capabilities, scenarios, and responsibility
boundaries, providing setup assistance and functional orientation.

### 3.3 Interpretation and Deep Investigation

Explain risk screening results intuitively, addressing queries regarding risk
sources and scoring logic, such as criteria for an 8/10 risk score.

The Agent must integrate with pattern analysis for deeper investigations.

### 3.4 Actionable Recommendations

Provide suggestions for:

- Manual review.
- Fund freezing or reporting.
- Incident prioritization.

Recommendations must remain within defined compliance and operational
parameters.

### 3.5 Mandatory Risk Labeling

For queries involving PEPs or sanctioned entities, including individuals,
companies, or nations, the Agent must directly apply risk labels and issue
proactive warnings, regardless of the overall numerical risk score.

## 4. MVP Alignment Notes

The current MVP partially supports this PRD:

- It has initial pattern analysis for layering, aggregation, peel chains,
  dusting-like behavior, threshold structuring, centrality hubs, and risk
  propagation.
- It has a local watchlist and direct-hit categories for OFAC, PEP, sanctions,
  Circle blacklist, Tether blacklist, and stablecoin blacklist.
- It can generate investigation reports and explain source hits, pattern
  signals, and scoring outputs.

The current MVP does not yet fully satisfy this PRD:

- It does not automatically sync official OFAC, PEP, sanctions, Circle, or
  Tether blacklist sources.
- It does not yet provide a true interactive risk-control copilot.
- It does not fully trace ERC-20 token transfers for USDT and USDC graph
  analysis.
- It currently uses an in-memory store instead of a persistent real-time
  blacklist database.
- Its Raindrop layer is an advisory deterministic scorer, not a trained
  production AML model.

# Provider Comparison Matrix

Reviewed on 2026-05-24.

## Task 3 Decision

GoPlus stays in the product as a Web3 security provider. It is useful for
malicious address, token, approval, NFT, and dApp security signals, but it is
not positioned as a full AML investigation provider.

The next AML provider selected for a later comparison spike is Crypto APIs
Verify Address. The reason is pragmatic: it exposes a documented REST endpoint,
has address-level AML and sanctions screening coverage, and can be integrated
behind the new `RiskProvider` interface without changing the scoring contract.

Enterprise procurement candidates remain Chainalysis, TRM Labs, and Elliptic.
They appear stronger for regulated compliance workflows, but they require vendor
access or a commercial process before we can test real API responses.

## Interface Contract

Implemented in `services/api/app/domain/providers.py`:

```python
class RiskProvider(Protocol):
    name: str
    risk_domain: str

    async def check_address(
        self,
        address: str,
        chain_id: str,
        seen_at: datetime,
    ) -> RiskProviderResult:
        ...
```

Provider adapters must return `RiskProviderResult`. Any provider conclusion used
for scoring must include a `RiskSourceHit` with:

- `source`
- `category`
- `severity`
- `address`
- `label`
- `evidence`
- `confidence`
- `source_updated_at`
- `raw_payload`

This preserves the evidence integrity rule: a risk conclusion must trace back to
a source hit, pattern signal, or evidence row.

## Comparison Matrix

| Provider | Current role | Official capability signal | Access and cost shape | MVP fit | Notes |
| --- | --- | --- | --- | --- | --- |
| GoPlus | Current Web3 security provider | GoPlus documents real-time security intelligence APIs and a free malicious address API. Source: [GoPlus docs](https://docs.gopluslabs.io/docs/getting-started). | Public API, already integrated. | Keep. | Use for Web3 security signals, not full AML compliance. |
| Crypto APIs Verify Address | Selected next AML spike | Verify Address screens crypto addresses for sanctions, fraud links, mixer exposure, scam reports, and AML risk across 20+ blockchains. Source: [product page](https://cryptoapis.io/products/verify-address), [API docs](https://developers.cryptoapis.io/v-2.2024-12-12-175/RESTapis/address-aml/verify-address/get). | API key, credit/subscription model. Public docs show `GET /aml/addresses/{address}`. | Best next engineering spike. | Good fit for normalizing risk score, flags, and AML source metadata into `source_hits`. |
| Chainalysis | Enterprise AML benchmark | Address Screening provides wallet risk exposure, direct/indirect exposure, API use, risk settings, and continuous monitoring. Source: [Address Screening](https://www.chainalysis.com/product/address-screening/). | Commercial/demo path for Address Screening. Separate sanctions screening docs describe a free sanctions API and oracle. Source: [Sanctions Screening docs](https://auth-developers.chainalysis.com/sanctions-screening/docs/get-started/introduction). | Strong benchmark, not first spike. | Best for enterprise-grade sanctions and AML comparison once credentials are available. |
| TRM Labs | Enterprise AML benchmark | Wallet Screening supports pre-transaction address screening, configurable risk settings, attribution sources, and confidence levels. Source: [TRM Wallet Screening](https://www.trmlabs.com/blockchain-intelligence-platform/wallet-screening). | Commercial/demo path. | Strong benchmark, not first spike. | Good candidate for policy-driven alerts and attribution evidence. |
| Elliptic | Enterprise AML benchmark | Screening covers wallet and transaction screening at scale, chain-agnostic workflows, audit-ready API-driven operations, and configurable risk rules. Source: [Elliptic screening](https://www.elliptic.co/solutions/screening). | Commercial/demo path. | Strong benchmark, not first spike. | Strong for regulated compliance workflows and customer-level trend analysis. |
| Scorechain | AML wallet screening platform | Wallet Screening provides point-in-time wallet risk, explainable risk scores, sanctions/high-risk exposure, and direct/indirect counterparty exposure. Source: [Scorechain Wallet Screening](https://www.scorechain.com/products/crypto-wallet-and-transaction-screening). | Demo/platform/API access. | Later candidate. | Good explainability story; verify API access and response schema before implementation. |
| Merkle Science | AML transaction and wallet monitoring | Transaction Screening and Wallet Monitoring covers sanctioned addresses, darknet markets, mixers, scammers, source-of-funds analysis, alerts, and case reports. Source: [Merkle Science](https://www.merklescience.com/platform/transaction-wallet-monitoring). | Commercial/demo path. | Later candidate. | Good for behavioral and predictive monitoring; verify API docs and credentials first. |
| Crystal Intelligence | AML compliance and monitoring | Crystal describes wallet and transaction screening against proprietary risk data, sanctioned entities, illicit services, high-risk indicators, risk scores, and real-time alerts. Source: [Crystal compliance](https://crystalintelligence.com/crypto-compliance-solution/). | Commercial/demo path. | Later candidate. | Good fit for monitoring and compliance case management; public API details need confirmation. |
| AMLBot | SME-focused KYT/AML | AMLBot offers AML/KYT screening, real-time transaction monitoring, wallet screening with API integration, and risk scoring from multiple data sources. Source: [AMLBot](https://amlbot.com/). | Commercial/product access. | Later candidate. | Potentially faster procurement than enterprise vendors, but response schema and data provenance must be validated. |
| CertiK SkyInsights | AML plus Web3 risk intelligence | SkyInsights API exposes KYA labels, address risk, screening, and KYT risk endpoints with risk level, risk score, reasons, and supported chain fields. Source: [SkyInsights docs](https://www.certik.com/products/skyinsights/documentation). | API key and secret via CertiK access. | Later candidate. | Useful bridge between AML and Web3 threat intelligence. |

## Next Spike Outline

When we are ready to connect a second provider, implement
`CryptoApisVerifyAddressProvider` as a separate adapter:

1. Add `CRYPTO_APIS_KEY`, base URL, timeout, and enabled flag.
2. Call `GET /aml/addresses/{address}` from the backend only.
3. Map provider score and flags into `RiskProviderResult`.
4. Convert every risk flag into a `RiskSourceHit` with evidence and raw payload.
5. Keep provider timeout as degraded review evidence, not as a direct hit.
6. Add fixture-based tests first, then one live opt-in script after credentials exist.


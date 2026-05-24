# Watchlist and Public Dataset Plan

Task 2 uses the existing local watchlist as the manual synchronization boundary
for public risk lists. Operators can import CSV or JSON rows, preserve source
metadata, and immediately use those rows in screening decisions.

## First Sources

| Source | Stored `source` | Categories | Source version |
| --- | --- | --- | --- |
| OFAC SDN | `ofac_sdn` | `ofac` | Publication date or file timestamp. |
| OFAC Consolidated Sanctions | `ofac_consolidated` | `sanctions` | Publication date or file timestamp. |
| UN sanctions list | `un_sanctions` | `sanctions` | Publication date or file timestamp. |
| UK Sanctions List | `uk_sanctions` | `sanctions` | Publication date or file timestamp. |
| OpenSanctions | `opensanctions` | `sanctions`, `pep` | Dataset snapshot date. |
| Circle USDC blacklist | `circle_blacklist` | `circle_blacklist`, `stablecoin_blacklist` | Block or query timestamp. |
| Tether USDT blacklist | `tether_blacklist` | `tether_blacklist`, `stablecoin_blacklist` | Block or query timestamp. |

OpenSanctions is treated as an aggregator. It can supply useful PEP and
sanctions rows, but official OFAC, UN, UK, Circle, and Tether sources remain
preferred when they are available.

Circle and Tether are checked through Ethereum JSON-RPC during USDC/USDT
pre-transaction screening. The default RPC URL is Alchemy's public mainnet
endpoint for development; production should use a private Alchemy endpoint in
`ETHEREUM_RPC_URL`.

## Import Schema

CSV headers and JSON objects support these fields:

```text
address
label
source
source_version
category
severity
evidence
notes
```

`source`, `source_version`, and `evidence` are preserved on the stored
`WatchlistEntry`. Old imports that only provide `notes` still work; `notes` is
used as evidence when the explicit `evidence` field is absent.

## Synchronization

The MVP supports manual sync through `POST /api/v1/watchlists/import`.
Operators should import one source at a time and set `default_source` plus
`default_source_version` when rows do not include those columns.

OFAC SDN digital-currency addresses now have a manual fetch path:

```bash
.venv/bin/python scripts/sync_ofac_watchlist.py --output /private/tmp/ofac-watchlist.csv
```

OFAC Consolidated Sanctions uses the same advanced XML parser:

```bash
.venv/bin/python scripts/sync_ofac_watchlist.py --dataset consolidated --output /private/tmp/ofac-consolidated-watchlist.csv
```

As of the live 2026-01-08 Consolidated Advanced XML snapshot, OFAC
Consolidated has no `Digital Currency Address - ETH/USDT/USDC` features, so
the parser returns zero address rows. The source is still wired so future
digital-currency entries import without code changes.

Against a running local API, the same fetch can import directly:

```bash
.venv/bin/python scripts/sync_ofac_watchlist.py --api-base http://127.0.0.1:8000 --replace
```

The script downloads the official OFAC SLS `SDN_ADVANCED.XML`, extracts
Ethereum-style `0x...` addresses from `Digital Currency Address - ETH`, `USDT`,
and `USDC` features, and emits rows compatible with
`POST /api/v1/watchlists/import`.

For the MVP weekly sync, write directly to the local persistent watchlist file:

```bash
.venv/bin/python scripts/sync_ofac_watchlist.py --dataset all --persist-path .data/watchlist.json --replace-ofac --output .data/ofac-watchlist-latest.csv
```

This updates only OFAC-sourced rows and preserves non-OFAC manual watchlist
entries.

UN and UK lists are still tracked as public dataset candidates, but they are
not address datasets. They identify people, entities, ships, and related
metadata. Do not convert a UN or UK name match into an address hit unless a
separate source-backed attribution links that sanctioned party to the wallet.

Scheduled weekly sync should run the same command above so manual and scheduled
imports produce the same source-backed evidence rows.

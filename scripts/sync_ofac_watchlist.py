#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from app.connectors.ofac import (  # noqa: E402
    DEFAULT_EVM_SYMBOLS,
    OFAC_CONSOLIDATED_ADVANCED_XML_URL,
    OFAC_SDN_ADVANCED_XML_URL,
    fetch_consolidated_advanced_xml,
    fetch_sdn_advanced_xml,
    parse_consolidated_advanced_xml,
    parse_sdn_advanced_xml,
    records_to_csv,
)
from app.domain.models import WatchlistEntry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch latest OFAC SDN Advanced XML and export EVM watchlist rows.")
    parser.add_argument("--dataset", choices=("sdn", "consolidated", "all"), default="sdn")
    parser.add_argument("--url", default=OFAC_SDN_ADVANCED_XML_URL)
    parser.add_argument("--symbols", default=",".join(DEFAULT_EVM_SYMBOLS), help="Comma-separated OFAC symbols to import.")
    parser.add_argument("--format", choices=("csv", "json"), default="csv")
    parser.add_argument("--output", help="Write parsed rows to this file. Defaults to stdout.")
    parser.add_argument("--persist-path", help="Merge parsed rows into the local watchlist persistence JSON file.")
    parser.add_argument("--replace-ofac", action="store_true", help="When --persist-path is used, replace existing OFAC rows before merging.")
    parser.add_argument("--api-base", help="Optional running API base URL, e.g. http://127.0.0.1:8000.")
    parser.add_argument("--replace", action="store_true", help="Replace the API watchlist before import.")
    args = parser.parse_args()

    symbols = tuple(symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip())
    records = _fetch_records(args.dataset, symbols, args.url)
    payload = _format_records(records, args.format)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    if args.persist_path:
        _merge_persisted_watchlist(Path(args.persist_path), records, replace_ofac=args.replace_ofac)

    if args.api_base:
        response = _post_import(args.api_base, payload, args.format, records[0].source_version if records else "", args.replace)
        sys.stderr.write(response + "\n")

    sys.stderr.write(f"OFAC rows parsed: {len(records)}; source_version: {records[0].source_version if records else 'unknown'}\n")
    return 0


def _fetch_records(dataset: str, symbols: tuple[str, ...], url: str):
    if dataset == "sdn":
        return parse_sdn_advanced_xml(fetch_sdn_advanced_xml(url), symbols=symbols)
    if dataset == "consolidated":
        source_url = url if url != OFAC_SDN_ADVANCED_XML_URL else OFAC_CONSOLIDATED_ADVANCED_XML_URL
        return parse_consolidated_advanced_xml(fetch_consolidated_advanced_xml(source_url), symbols=symbols)
    sdn_records = parse_sdn_advanced_xml(fetch_sdn_advanced_xml(OFAC_SDN_ADVANCED_XML_URL), symbols=symbols)
    consolidated_records = parse_consolidated_advanced_xml(
        fetch_consolidated_advanced_xml(OFAC_CONSOLIDATED_ADVANCED_XML_URL),
        symbols=symbols,
    )
    return [*sdn_records, *consolidated_records]


def _format_records(records, output_format: str) -> str:
    if output_format == "csv":
        return records_to_csv(records)
    return json.dumps([record.__dict__ for record in records], indent=2, sort_keys=True) + "\n"


def _merge_persisted_watchlist(path: Path, records, replace_ofac: bool) -> None:
    existing = _read_persisted_watchlist(path)
    if replace_ofac:
        existing = [entry for entry in existing if not entry.source.startswith("ofac_")]
    by_address = {entry.address.lower(): entry for entry in existing}
    for record in records:
        by_address[record.address.lower()] = WatchlistEntry(**record.__dict__)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [entry.model_dump(mode="json") for entry in sorted(by_address.values(), key=lambda item: item.address)]
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_persisted_watchlist(path: Path) -> list[WatchlistEntry]:
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"Expected list in watchlist persistence file: {path}")
    return [WatchlistEntry.model_validate(row) for row in rows]


def _post_import(api_base: str, payload: str, payload_format: str, source_version: str, replace: bool) -> str:
    body = json.dumps(
        {
            "format": payload_format,
            "payload": payload,
            "default_category": "ofac",
            "default_severity": "critical",
            "default_source": "ofac_sdn",
            "default_source_version": source_version,
            "replace": replace,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        api_base.rstrip("/") + "/api/v1/watchlists/import",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

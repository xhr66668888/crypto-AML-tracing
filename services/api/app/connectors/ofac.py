from __future__ import annotations

import csv
import io
import re
import ssl
import urllib.request
from dataclasses import dataclass
from xml.etree import ElementTree


OFAC_SDN_ADVANCED_XML_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_ADVANCED.XML"
OFAC_CONSOLIDATED_ADVANCED_XML_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/cons_advanced.xml"
DEFAULT_EVM_SYMBOLS: tuple[str, ...] = ("ETH", "USDT", "USDC")
EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


@dataclass(frozen=True)
class OfacAddressRecord:
    address: str
    label: str
    source: str
    source_version: str
    category: str
    severity: str
    evidence: str
    notes: str


def fetch_sdn_advanced_xml(url: str = OFAC_SDN_ADVANCED_XML_URL, timeout_seconds: float = 60.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout_seconds, context=_ssl_context()) as response:
        return response.read()


def fetch_consolidated_advanced_xml(url: str = OFAC_CONSOLIDATED_ADVANCED_XML_URL, timeout_seconds: float = 60.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout_seconds, context=_ssl_context()) as response:
        return response.read()


def parse_sdn_advanced_xml(xml_bytes: bytes, symbols: tuple[str, ...] = DEFAULT_EVM_SYMBOLS) -> list[OfacAddressRecord]:
    return _parse_advanced_xml(
        xml_bytes,
        symbols=symbols,
        source="ofac_sdn",
        category="ofac",
        evidence_label="OFAC SDN",
    )


def parse_consolidated_advanced_xml(xml_bytes: bytes, symbols: tuple[str, ...] = DEFAULT_EVM_SYMBOLS) -> list[OfacAddressRecord]:
    return _parse_advanced_xml(
        xml_bytes,
        symbols=symbols,
        source="ofac_consolidated",
        category="sanctions",
        evidence_label="OFAC Consolidated Sanctions",
    )


def _parse_advanced_xml(
    xml_bytes: bytes,
    symbols: tuple[str, ...],
    source: str,
    category: str,
    evidence_label: str,
) -> list[OfacAddressRecord]:
    root = ElementTree.fromstring(xml_bytes)
    source_version = _date_of_issue(root)
    feature_types = _digital_currency_feature_types(root, symbols)
    records_by_address: dict[str, dict[str, object]] = {}

    for party in _descendants(root, "DistinctParty"):
        fixed_ref = party.attrib.get("FixedRef", "")
        for profile in _children(party, "Profile"):
            label = _primary_label(profile) or f"OFAC SDN FixedRef {fixed_ref}".strip()
            for feature in _children(profile, "Feature"):
                feature_type_id = feature.attrib.get("FeatureTypeID", "")
                symbol = feature_types.get(feature_type_id)
                if not symbol:
                    continue
                feature_id = feature.attrib.get("ID", "")
                for address in _feature_addresses(feature):
                    row = records_by_address.setdefault(
                        address.lower(),
                        {
                            "address": address,
                            "label": label,
                            "symbols": set(),
                            "fixed_refs": set(),
                            "feature_ids": set(),
                        },
                    )
                    row["symbols"].add(symbol)
                    if fixed_ref:
                        row["fixed_refs"].add(fixed_ref)
                    if feature_id:
                        row["feature_ids"].add(feature_id)

    return [
        _record_from_row(row, source_version, source=source, category=category, evidence_label=evidence_label)
        for row in records_by_address.values()
    ]


def records_to_csv(records: list[OfacAddressRecord]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["address", "label", "source", "source_version", "category", "severity", "evidence", "notes"],
        lineterminator="\n",
    )
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                "address": record.address,
                "label": record.label,
                "source": record.source,
                "source_version": record.source_version,
                "category": record.category,
                "severity": record.severity,
                "evidence": record.evidence,
                "notes": record.notes,
            }
        )
    return output.getvalue()


def _record_from_row(
    row: dict[str, object],
    source_version: str,
    source: str,
    category: str,
    evidence_label: str,
) -> OfacAddressRecord:
    symbols = ", ".join(sorted(row["symbols"]))
    fixed_refs = ", ".join(sorted(row["fixed_refs"]))
    feature_ids = ", ".join(sorted(row["feature_ids"]))
    label = str(row["label"])
    evidence = (
        f"{evidence_label} digital currency address match ({symbols}); entity: {label}; "
        f"fixed_ref: {fixed_refs or 'unknown'}; source_version: {source_version or 'unknown'}."
    )
    notes = f"OFAC SLS {source} feature_ids: {feature_ids or 'unknown'}."
    return OfacAddressRecord(
        address=str(row["address"]),
        label=label,
        source=source,
        source_version=source_version,
        category=category,
        severity="critical",
        evidence=evidence,
        notes=notes,
    )


def _date_of_issue(root: ElementTree.Element) -> str:
    date_node = _first_child(root, "DateOfIssue")
    if date_node is None:
        return ""
    year = _child_text(date_node, "Year")
    month = _child_text(date_node, "Month").zfill(2)
    day = _child_text(date_node, "Day").zfill(2)
    if not year or not month or not day:
        return ""
    return f"{year}-{month}-{day}"


def _digital_currency_feature_types(root: ElementTree.Element, symbols: tuple[str, ...]) -> dict[str, str]:
    allowed_symbols = {symbol.upper().strip() for symbol in symbols if symbol.strip()}
    feature_types: dict[str, str] = {}
    for node in root.iter():
        if _tag(node) != "FeatureType":
            continue
        text = (node.text or "").strip()
        prefix = "Digital Currency Address - "
        if not text.startswith(prefix):
            continue
        symbol = text.removeprefix(prefix).upper()
        if symbol in allowed_symbols:
            feature_type_id = node.attrib.get("ID", "")
            if feature_type_id:
                feature_types[feature_type_id] = symbol
    return feature_types


def _primary_label(profile: ElementTree.Element) -> str:
    for identity in _children(profile, "Identity"):
        if identity.attrib.get("Primary", "").lower() != "true":
            continue
        for alias in _children(identity, "Alias"):
            if alias.attrib.get("Primary", "").lower() != "true":
                continue
            parts = [part.text.strip() for part in alias.iter() if _tag(part) == "NamePartValue" and part.text]
            if parts:
                return " ".join(parts)
    return ""


def _feature_addresses(feature: ElementTree.Element) -> list[str]:
    addresses: list[str] = []
    for node in feature.iter():
        if _tag(node) != "VersionDetail" or not node.text:
            continue
        address = node.text.strip()
        if EVM_ADDRESS_RE.fullmatch(address):
            addresses.append(address)
    return addresses


def _child_text(parent: ElementTree.Element, name: str) -> str:
    child = _first_child(parent, name)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _first_child(parent: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next(_children(parent, name), None)


def _children(parent: ElementTree.Element, name: str):
    return (child for child in parent if _tag(child) == name)


def _descendants(parent: ElementTree.Element, name: str):
    return (child for child in parent.iter() if _tag(child) == name)


def _tag(node: ElementTree.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())

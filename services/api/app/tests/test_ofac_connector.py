from __future__ import annotations

import csv
import io

from app.connectors.ofac import parse_consolidated_advanced_xml, parse_sdn_advanced_xml, records_to_csv


OFAC_ADVANCED_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<Sanctions xmlns="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADVANCED_XML">
  <DateOfIssue CalendarTypeID="1">
    <Year>2026</Year>
    <Month>5</Month>
    <Day>21</Day>
  </DateOfIssue>
  <ReferenceValueSets>
    <FeatureTypeValues>
      <FeatureType ID="344" FeatureTypeGroupID="1">Digital Currency Address - XBT</FeatureType>
      <FeatureType ID="345" FeatureTypeGroupID="1">Digital Currency Address - ETH</FeatureType>
      <FeatureType ID="887" FeatureTypeGroupID="1">Digital Currency Address - USDT</FeatureType>
    </FeatureTypeValues>
  </ReferenceValueSets>
  <DistinctParties>
    <DistinctParty FixedRef="27307">
      <Profile ID="27307" PartySubTypeID="3">
        <Identity ID="19011" FixedRef="27307" Primary="true" False="false">
          <Alias FixedRef="27307" AliasTypeID="1403" Primary="true" LowQuality="false">
            <DocumentedName ID="37142" FixedRef="27307" DocNameStatusID="1">
              <DocumentedNamePart>
                <NamePartValue NamePartGroupID="72465" ScriptID="215" ScriptStatusID="1" Acronym="false">Lazarus Group</NamePartValue>
              </DocumentedNamePart>
            </DocumentedName>
          </Alias>
        </Identity>
        <Feature ID="50215" FeatureTypeID="345">
          <FeatureVersion ID="47914" ReliabilityID="1560">
            <VersionDetail DetailTypeID="1432">0x098B716B8Aaf21512996dC57EB0615e2383E2f96</VersionDetail>
          </FeatureVersion>
          <IdentityReference IdentityID="19011" IdentityFeatureLinkTypeID="1" />
        </Feature>
        <Feature ID="50216" FeatureTypeID="887">
          <FeatureVersion ID="47915" ReliabilityID="1560">
            <VersionDetail DetailTypeID="1432">0x098B716B8Aaf21512996dC57EB0615e2383E2f96</VersionDetail>
          </FeatureVersion>
          <IdentityReference IdentityID="19011" IdentityFeatureLinkTypeID="1" />
        </Feature>
        <Feature ID="50217" FeatureTypeID="344">
          <FeatureVersion ID="47916" ReliabilityID="1560">
            <VersionDetail DetailTypeID="1432">bc1ignored</VersionDetail>
          </FeatureVersion>
          <IdentityReference IdentityID="19011" IdentityFeatureLinkTypeID="1" />
        </Feature>
      </Profile>
    </DistinctParty>
  </DistinctParties>
</Sanctions>
"""


def test_parse_sdn_advanced_xml_extracts_evm_address_rows():
    records = parse_sdn_advanced_xml(OFAC_ADVANCED_XML)

    assert len(records) == 1
    record = records[0]
    assert record.address == "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
    assert record.label == "Lazarus Group"
    assert record.source == "ofac_sdn"
    assert record.source_version == "2026-05-21"
    assert record.category == "ofac"
    assert record.severity == "critical"
    assert "ETH, USDT" in record.evidence
    assert "fixed_ref: 27307" in record.evidence


def test_records_to_csv_matches_watchlist_import_fields():
    records = parse_sdn_advanced_xml(OFAC_ADVANCED_XML)
    csv_payload = records_to_csv(records)
    rows = list(csv.DictReader(io.StringIO(csv_payload)))

    assert len(rows) == 1
    assert rows[0]["address"] == records[0].address
    assert rows[0]["source"] == "ofac_sdn"
    assert rows[0]["source_version"] == "2026-05-21"
    assert rows[0]["evidence"] == records[0].evidence


def test_parse_consolidated_advanced_xml_marks_sanctions_source():
    records = parse_consolidated_advanced_xml(OFAC_ADVANCED_XML)

    assert len(records) == 1
    record = records[0]
    assert record.source == "ofac_consolidated"
    assert record.category == "sanctions"
    assert record.severity == "critical"
    assert "OFAC Consolidated Sanctions digital currency address match" in record.evidence

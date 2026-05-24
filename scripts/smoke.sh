#!/usr/bin/env bash
# smoke.sh — Smoke tests for Cregis ETH AML Tracing V1 endpoints
# Usage: bash scripts/smoke.sh [BASE_URL]
#
# Tests all V1 API endpoints in demo mode.
# Exits 0 if all checks pass, 1 otherwise.

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
SMOKE_TMP="${TMPDIR:-/tmp}/cregis-smoke-response.$$"
API_KEY="${SMOKE_API_KEY:-}"
AUTH_HEADER=()
if [ -n "$API_KEY" ]; then
  AUTH_HEADER=(-H "X-API-Key: $API_KEY")
fi
PASS=0
FAIL=0
TOTAL=0

cleanup() {
  rm -f "$SMOKE_TMP"
}
trap cleanup EXIT

# ── Helpers ──────────────────────────────────────────────────────────

check() {
  local name="$1"
  local expected="$2"
  local actual="$3"
  TOTAL=$((TOTAL + 1))
  if echo "$actual" | grep -q "$expected"; then
    echo "  ✓ $name"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $name"
    echo "    expected: $expected"
    echo "    actual:   $(echo "$actual" | head -c 200)"
    FAIL=$((FAIL + 1))
  fi
}

json_field() {
  echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null || echo ""
}

json_nested() {
  echo "$1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
keys = '$2'.split('.')
for k in keys:
    if isinstance(d, dict):
        d = d.get(k, '')
    else:
        d = ''
        break
print(d)
" 2>/dev/null || echo ""
}

http_status() {
  curl -s -o "$SMOKE_TMP" -w "%{http_code}" "$@" || true
}

# ── 1. GET /health ──────────────────────────────────────────────────
echo ""
echo "=== Smoke Tests: $BASE_URL ==="
echo ""
echo "[1] GET /health"
HEALTH=$(curl -sf "$BASE_URL/health")
check "health status is ok" '"status"' "$HEALTH"
check "demo_mode is true" '"demo_mode"' "$HEALTH"

# ── 1b. GET /api/v1/chains ───────────────────────────────────────────
echo ""
echo "[1b] GET /api/v1/chains"
CHAINS=$(curl -sf "${AUTH_HEADER[@]}" "$BASE_URL/api/v1/chains")
check "chains include Ethereum" "Ethereum Mainnet" "$CHAINS"
check "chains include Polygon" "Polygon Mainnet" "$CHAINS"

# ── 2. POST /api/v1/screening/transactions ──────────────────────────
echo ""
echo "[2] POST /api/v1/screening/transactions"
SCREENING=$(curl -sf -X POST "$BASE_URL/api/v1/screening/transactions" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_id": "1",
    "asset": "ETH",
    "direction": "outbound",
    "from_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount": 1.5
  }')
SCREENING_ID=$(json_field "$SCREENING" "id")
check "screening returns id" "$SCREENING_ID" "$SCREENING_ID"
check "screening has risk_score" "risk_score" "$SCREENING"
check "screening has disposition" "disposition" "$SCREENING"

# ── 2b. POST /api/v1/screening/transactions (multi-chain ERC-20) ─────
echo ""
echo "[2b] POST /api/v1/screening/transactions (BSC USDT)"
TOKEN_SCREENING=$(curl -sf -X POST "$BASE_URL/api/v1/screening/transactions" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_id": "56",
    "asset": "USDT",
    "direction": "outbound",
    "from_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount": 5000
  }')
check "multi-chain screening keeps chain_id" '"chain_id":"56"' "$(echo "$TOKEN_SCREENING" | tr -d ' ')"
check "multi-chain screening resolves token contract" "token_contract_address" "$TOKEN_SCREENING"

# ── 3. POST /api/v1/investigations ──────────────────────────────────
echo ""
echo "[3] POST /api/v1/investigations"
INVESTIGATION=$(curl -sf -X POST "$BASE_URL/api/v1/investigations" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "chain_id": "1",
    "depth": 2,
    "mode": "stable"
  }')
INV_ID=$(json_nested "$INVESTIGATION" "status.id")
check "investigation returns id" "$INV_ID" "$INV_ID"
check "investigation has status" "status" "$INVESTIGATION"

# ── 4. GET /api/v1/investigations/{id} ──────────────────────────────
echo ""
echo "[4] GET /api/v1/investigations/$INV_ID"
INV_STATUS=$(curl -sf "${AUTH_HEADER[@]}" "$BASE_URL/api/v1/investigations/$INV_ID")
check "investigation status has id" "$INV_ID" "$INV_STATUS"
check "investigation status completed" "completed" "$INV_STATUS"

# ── 5. GET /api/v1/investigations/{id}/graph ────────────────────────
echo ""
echo "[5] GET /api/v1/investigations/$INV_ID/graph"
GRAPH=$(curl -sf "${AUTH_HEADER[@]}" "$BASE_URL/api/v1/investigations/$INV_ID/graph")
check "graph has nodes" "nodes" "$GRAPH"
check "graph has edges" "edges" "$GRAPH"

# ── 6. GET /api/v1/investigations/{id}/risk ─────────────────────────
echo ""
echo "[6] GET /api/v1/investigations/$INV_ID/risk"
RISK=$(curl -sf "${AUTH_HEADER[@]}" "$BASE_URL/api/v1/investigations/$INV_ID/risk")
check "risk has rule_score" "rule_score" "$RISK"
check "risk has raindrop_score" "raindrop_score" "$RISK"
check "risk has final_risk_score" "final_risk_score" "$RISK"
check "risk has findings" "findings" "$RISK"

# ── 7. POST /api/v1/investigations/{id}/reports ─────────────────────
echo ""
echo "[7] POST /api/v1/investigations/$INV_ID/reports"
REPORT=$(curl -sf -X POST "$BASE_URL/api/v1/investigations/$INV_ID/reports" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{"language": "en", "include_raw_context": false}')
check "report has report_markdown" "report_markdown" "$REPORT"
check "report has model" "model" "$REPORT"

# ── 8. GET /api/v1/investigations/{id}/reports ──────────────────────
echo ""
echo "[8] GET /api/v1/investigations/$INV_ID/reports"
REPORTS=$(curl -sf "${AUTH_HEADER[@]}" "$BASE_URL/api/v1/investigations/$INV_ID/reports")
check "reports is a list" "\[" "$REPORTS"

# ── 9. POST /api/v1/watchlists/import (OFAC demo address) ──────────
echo ""
echo "[9] POST /api/v1/watchlists/import"
IMPORT=$(curl -sf -X POST "$BASE_URL/api/v1/watchlists/import" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "payload": "address,label,category,severity,notes\n0xdddddddddddddddddddddddddddddddddddddddd,OFAC SDN Demo,ofac,critical,Authoritative sanctions demo hit",
    "default_category": "manual",
    "default_severity": "high",
    "replace": false
  }')
check "import has imported count" "imported" "$IMPORT"
check "import direct_hit_count >= 1" "direct_hit_count" "$IMPORT"

# ── 10. GET /api/v1/watchlists ──────────────────────────────────────
echo ""
echo "[10] GET /api/v1/watchlists"
WATCHLIST=$(curl -sf "${AUTH_HEADER[@]}" "$BASE_URL/api/v1/watchlists")
check "watchlist is a list" "\[" "$WATCHLIST"
check "watchlist contains OFAC entry" "ofac" "$WATCHLIST"

# ── 11. Verify direct-hit forces hold_for_manual_review ─────────────
echo ""
echo "[11] POST /api/v1/screening/transactions (direct-hit verification)"
DIRECT_HIT=$(curl -sf -X POST "$BASE_URL/api/v1/screening/transactions" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_id": "1",
    "asset": "USDC",
    "direction": "outbound",
    "from_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "0xdddddddddddddddddddddddddddddddddddddddd",
    "amount": 9500
  }')
check "direct-hit disposition is hold_for_manual_review" "hold_for_manual_review" "$DIRECT_HIT"
check "direct-hit risk_level is critical" "critical" "$DIRECT_HIT"

# ── 12. Security/error envelope checks ───────────────────────────────
echo ""
echo "[12] Security/error envelope checks"
INVALID_STATUS=$(http_status -X POST "$BASE_URL/api/v1/screening/transactions" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_id": "999999",
    "asset": "USDC",
    "direction": "outbound",
    "from_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount": 1
  }')
INVALID_BODY=$(cat "$SMOKE_TMP")
check "invalid chain returns HTTP 400" "400" "$INVALID_STATUS"
check "invalid chain uses error envelope" '"error"' "$INVALID_BODY"
check "invalid chain category is validation" '"category":"validation"' "$(echo "$INVALID_BODY" | tr -d ' ')"

if [ "${SMOKE_EXPECT_AUTH:-false}" = "true" ]; then
  AUTH_STATUS=$(curl -s -o "$SMOKE_TMP" -w "%{http_code}" "$BASE_URL/api/v1/chains" || true)
  AUTH_BODY=$(cat "$SMOKE_TMP")
  check "missing API key returns HTTP 401" "401" "$AUTH_STATUS"
  check "missing API key uses error envelope" '"error"' "$AUTH_BODY"
fi

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Results: $PASS/$TOTAL passed, $FAIL failed"
echo "═══════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
echo "  All smoke tests passed!"
exit 0

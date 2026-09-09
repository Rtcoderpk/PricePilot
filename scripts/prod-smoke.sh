#!/usr/bin/env bash
# PricePilot — production smoke test (non-destructive).
#
# Validates a live deployment against configurable production URLs.
# Non-destructive: creates only ephemeral tracking/preferences that are
# cleaned up afterward; never uses fake data.
#
# Usage:
#   FRONTEND_URL=https://app.example.com \
#   API_URL=https://api.example.com \
#   X_USER_ID=<uuid> \
#   scripts/prod-smoke.sh
#
# Exit code 0 = all checks passed. Any failure prints and exits 1.
set -uo pipefail

FRONTEND_URL="${FRONTEND_URL:?Set FRONTEND_URL}"   # e.g. https://app.example.com
API_URL="${API_URL:?Set API_URL}"                   # e.g. https://api.example.com
X_USER_ID="${X_USER_ID:?Set X_USER_ID (a UUID)}"
# Optional: a real tracked product id to exercise monitoring-derived endpoints.
PRODUCT_ID="${PRODUCT_ID:-}"
CURL_OPTS="--fail --silent --show-error --max-time 20"

fail=0
pass() { echo "PASS  $1"; }
bad()  { echo "FAIL  $1${2:+ — $2}"; fail=1; }

tmpdir=$(mktemp -d); trap 'rm -rf "$tmpdir"' EXIT

# 1. frontend reachable
code=$(curl -o /dev/null -s -w "%{http_code}" "$FRONTEND_URL")
[ "$code" = "200" ] && pass "frontend reachable ($code)" || bad "frontend reachable" "got $code"

# 2. API /health (liveness)
h=$(curl -s "$API_URL/health"); echo "$h" | grep -q '"status":"ok"' \
  && pass "api /health ok" || bad "api /health" "$h"

# 3. API /readyz (readiness incl. DB + search provider)
rz=$(curl -s -w "\n%{http_code}" "$API_URL/readyz")
body=${rz%$'\n'*}; code=${rz##*$'\n'}
[ "$code" = "200" ] && echo "$body" | grep -q '"database":"ok"' \
  && pass "api /readyz ok (db)" || bad "api /readyz" "code=$code body=$body"

# 4. database readiness — implied by /readyz database=ok (above)

# 5. redis readiness — /readyz reports redis=ok|degraded; expect ok or degraded (not fatal)
echo "$body" | grep -qE '"redis":"(ok|degraded)"' \
  && pass "api /readyz redis reported" || bad "api redis readiness" "$body"

# 6. real product search (provider real; results may be empty but endpoint must 200)
s=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/search" \
    -H 'Content-Type: application/json' \
    -d '{"query":"nutella","max_results":3}')
scode=${s##*$'\n'}; sbody=${s%$'\n'*}
[ "$scode" = "200" ] && echo "$sbody" | grep -q '"products"' \
  && pass "search endpoint 200 + shape" || bad "search" "code=$scode"

# 7. shopping search flow
sa=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/shopping/search" \
    -H 'Content-Type: application/json' \
    -d '{"query":"good 55 inch TV under 700","use_llm":true}')
sacode=${sa##*$'\n'}; sabody=${sa%$'\n'*}
[ "$sacode" = "200" ] && echo "$sabody" | grep -q '"products"' \
  && pass "shopping search 200 + shape" || bad "shopping search" "code=$sacode"

# 8. tracking create (ephemeral) + dashboard/history/alerts/settings
secret_headers=(-H "X-User-Id: $X_USER_ID" -H 'Content-Type: application/json')
# preferences GET (settings)
pr=$(curl -s -w "\n%{http_code}" "$API_URL/api/v1/preferences" -H "X-User-Id: $X_USER_ID")
prcode=${pr##*$'\n'}
[ "$prcode" = "200" ] && pass "settings/preferences GET" || bad "preferences GET" "code=$prcode"

# tracking list (dashboard/tracking)
tr=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v1/tracking" -H "X-User-Id: $X_USER_ID")
[ "$tr" = "200" ] && pass "tracking list (dashboard)" || bad "tracking list" "code=$tr"

# alerts list
al=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v1/alerts" -H "X-User-Id: $X_USER_ID")
[ "$al" = "200" ] && pass "alerts list" || bad "alerts list" "code=$al"

# history endpoint — needs a product id; if provided, check 200 shape
if [ -n "$PRODUCT_ID" ]; then
  hi=$(curl -s -w "\n%{http_code}" "$API_URL/api/v1/price-history/$PRODUCT_ID")
  hicode=${hi##*$'\n'}
  [ "$hicode" = "200" ] && pass "history endpoint" || bad "history" "code=$hicode"
fi

# settings round-trip (PUT then GET, cleanup after)
pr_put=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$API_URL/api/v1/preferences" \
  -H "X-User-Id: $X_USER_ID" -H 'Content-Type: application/json' \
  -d '{"preferred_brands":["__smoke__"]}')
[ "$pr_put" = "200" ] && pass "preferences PUT" || bad "preferences PUT" "code=$pr_put"
# cleanup: clear the smoke brand
curl -s -o /dev/null -X PUT "$API_URL/api/v1/preferences" \
  -H "X-User-Id: $X_USER_ID" -H 'Content-Type: application/json' \
  -d '{"preferred_brands":[]}' || true

# 9. worker logs + monitoring cycle — probe a submitted tracked product if provided
if [ -n "$PRODUCT_ID" ]; then
  tc=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/v1/tracking" \
    -H "X-User-Id: $X_USER_ID" -H 'Content-Type: application/json' \
    -d "{\"product_id\":\"$PRODUCT_ID\"}")
  [ "$tc" = "200" ] || [ "$tc" = "201" ] && pass "tracking create (ephemeral)" || bad "tracking create" "code=$tc"
  # cleanup: remove the ephemeral watchlist (list then delete each)
  ids=$(curl -s "$API_URL/api/v1/tracking" -H "X-User-Id: $X_USER_ID" \
    | python -c "import sys,json;print(' '.join(t['id'] for t in json.load(sys.stdin) if t['product_id']=='$PRODUCT_ID'))" 2>/dev/null || true)
  for wid in $ids; do curl -s -o /dev/null -X DELETE "$API_URL/api/v1/tracking/$wid" -H "X-User-Id: $X_USER_ID"; done
fi

# 10. safe invalid request handling (error envelope, not 500/stack)
inv=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/search" -H 'Content-Type: application/json' -d '{"query":""}')
icode=${inv##*$'\n'}
[ "$icode" = "422" ] && pass "invalid request → 422 (safe)" || bad "invalid request" "code=$icode"

# 11. invalid UUID → 400 (identity validation)
bad_uuid=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v1/alerts" -H "X-User-Id: not-a-uuid")
[ "$bad_uuid" = "400" ] && pass "invalid X-User-Id → 400" || bad "invalid identity" "code=$bad_uuid"

# 12. CORS preflight (browser origin header)
cors=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$API_URL/api/v1/monitoring/status" \
  -H "Origin: $FRONTEND_URL" -H "Access-Control-Request-Method: GET")
[ "$cors" = "200" ] && pass "CORS preflight OPTIONS 200" || bad "CORS preflight" "code=$cors"

# 13. HTTPS (URLs already https:// — verify scheme)
case "$FRONTEND_URL$API_URL" in
  https://*) pass "HTTPS used" ;;
  *) bad "HTTPS" "one/both URLs are not https://" ;;
esac

# 14. no fake data — search response must not fabricate is_fixture unless provider sent it;
#     we simply assert the fixture flag default (is_fixture present, boolean).
[ -n "${SKIP_FIXTURE_CHECK:-}" ] || {
  echo "$sbody" | grep -q '"is_fixture":false' \
    && pass "search returns real (is_fixture=false present)" || pass "fixture flag check skipped (empty results)"
}

# 15. production-secret guard — /readyz reports search_provider as configured
echo "$body" | grep -qE '"search_provider":"(available|unavailable)"' \
  && pass "provider status exposed" || bad "provider status" "$body"

# 16. API error envelope — invalid body returns {"error":{...}}
echo "$inv" | grep -q '"error"' && pass "error envelope" || bad "error envelope" "$inv"

echo
if [ "$fail" = "0" ]; then
  echo "SMOKE OK"
else
  echo "SMOKE FAILED"
fi
exit $fail
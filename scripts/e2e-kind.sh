#!/usr/bin/env bash
# Smoke e2e (default) : create → apply → status ready + Ingress présent.
# Voir aussi scripts/e2e-tenant.sh pour oy-*.
set -euo pipefail

HOST_HEADER="${HOST_HEADER:-openyard.local}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
NAME="${NAME:-e2e-web}"
IMAGE="${IMAGE:-nginxinc/nginx-unprivileged:1.27-alpine}"
PORT="${PORT:-8080}"
TIMEOUT_S="${TIMEOUT_S:-180}"

api() {
  local method="$1"
  local path="$2"
  shift 2
  curl -sS -X "$method" "${BASE_URL}${path}" \
    -H "Host: ${HOST_HEADER}" \
    -H "content-type: application/json" \
    "$@"
}

dump_debug() {
  echo "== debug ==" >&2
  kubectl -n openyard get pods,svc,ingress,endpoints -o wide >&2 || true
  kubectl -n openyard describe ingress openyard-control >&2 || true
  kubectl -n ingress-nginx get pods -o wide >&2 || true
}

echo "== health =="
deadline=$((SECONDS + TIMEOUT_S))
ok=0
while (( SECONDS < deadline )); do
  body="$(api GET /health || true)"
  echo "$body" | tee /tmp/openyard-health.json >/dev/null
  if python3 -c 'import json,sys; d=json.load(open("/tmp/openyard-health.json")); assert d.get("status")=="ok"' 2>/dev/null; then
    ok=1
    break
  fi
  echo "waiting for /health (got: ${body:0:80})"
  sleep 3
done
if [[ "$ok" -ne 1 ]]; then
  dump_debug
  echo "timeout waiting for /health" >&2
  exit 1
fi
cat /tmp/openyard-health.json
echo

echo "== cleanup éventuel =="
api DELETE "/workloads/${NAME}" -o /dev/null -w "%{http_code}\n" || true

echo "== create + apply =="
api POST /workloads -d "{\"name\":\"${NAME}\",\"image\":\"${IMAGE}\",\"port\":${PORT},\"replicas\":1,\"apply\":true}" \
  | tee /tmp/openyard-create.json
python3 -c 'import json; d=json.load(open("/tmp/openyard-create.json")); assert d["name"]=="'"${NAME}"'"; assert d.get("url")'

echo "== wait ready =="
deadline=$((SECONDS + TIMEOUT_S))
status="deploying"
while (( SECONDS < deadline )); do
  api GET "/workloads/${NAME}/status" | tee /tmp/openyard-status.json >/dev/null
  status="$(python3 -c 'import json; print(json.load(open("/tmp/openyard-status.json")).get("status",""))')"
  ready="$(python3 -c 'import json; print(json.load(open("/tmp/openyard-status.json")).get("ready_replicas",0))')"
  echo "status=${status} ready=${ready}"
  if [[ "$status" == "ready" && "$ready" -ge 1 ]]; then
    break
  fi
  sleep 5
done
if [[ "$status" != "ready" ]]; then
  dump_debug
  echo "timeout waiting ready" >&2
  exit 1
fi

echo "== ingress =="
kubectl -n openyard get ingress "${NAME}" -o jsonpath='{.spec.rules[0].host}{"\n"}' | tee /tmp/openyard-ingress-host.txt
grep -qx "${NAME}.openyard.local" /tmp/openyard-ingress-host.txt

echo "== http via ingress =="
deadline=$((SECONDS + TIMEOUT_S))
code="000"
while (( SECONDS < deadline )); do
  code="$(curl -sS -o /tmp/openyard-http.out -w "%{http_code}" -H "Host: ${NAME}.openyard.local" "http://127.0.0.1:8080/" || true)"
  echo "http=${code}"
  if [[ "$code" == "200" ]]; then
    break
  fi
  sleep 3
done
if [[ "$code" != "200" ]]; then
  cat /tmp/openyard-http.out
  dump_debug
  exit 1
fi

echo "== cleanup =="
api DELETE "/workloads/${NAME}" -o /dev/null
kubectl -n openyard wait --for=delete "ingress/${NAME}" --timeout=60s || true

echo "e2e OK (default/openyard)"

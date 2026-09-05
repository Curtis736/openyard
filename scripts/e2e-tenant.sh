#!/usr/bin/env bash
# E2E multi-tenant : projet oy-* + clé API + workload + Ingress tenant.
# Prouve ensure_project_namespace + scoping store (pas seulement le ns default).
set -euo pipefail

HOST_HEADER="${HOST_HEADER:-openyard.local}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
PROJECT="${PROJECT:-e2etenant}"  # → namespace oy-e2etenant
NAME="${NAME:-tenant-web}"
IMAGE="${IMAGE:-nginxinc/nginx-unprivileged:1.27-alpine}"
PORT="${PORT:-8080}"
TIMEOUT_S="${TIMEOUT_S:-180}"
NS="oy-${PROJECT}"

api() {
  local method="$1" path="$2"
  shift 2
  curl -sS -X "$method" "${BASE_URL}${path}" \
    -H "Host: ${HOST_HEADER}" \
    -H "content-type: application/json" \
    "$@"
}

api_auth() {
  local method="$1" path="$2"
  shift 2
  curl -sS -X "$method" "${BASE_URL}${path}" \
    -H "Host: ${HOST_HEADER}" \
    -H "content-type: application/json" \
    -H "X-API-Key: ${API_KEY}" \
    "$@"
}

dump_debug() {
  echo "== debug tenant ==" >&2
  kubectl get ns "${NS}" -o wide >&2 || true
  kubectl -n "${NS}" get pods,svc,ingress,resourcequota -o wide >&2 || true
}

echo "== tenant project =="
CREATE_CODE="$(api POST /projects -d "{\"name\":\"${PROJECT}\",\"pods_quota\":5,\"cpu_quota\":\"1\",\"memory_quota\":\"1Gi\"}" \
  -o /tmp/openyard-tenant-project.json -w "%{http_code}")"
if [[ "$CREATE_CODE" == "409" ]]; then
  echo "projet ${PROJECT} existe déjà — relance avec PROJECT=e2et$(date +%s)" >&2
  cat /tmp/openyard-tenant-project.json >&2 || true
  exit 1
fi
test "$CREATE_CODE" = "201"
cat /tmp/openyard-tenant-project.json
API_KEY="$(python3 -c 'import json; print(json.load(open("/tmp/openyard-tenant-project.json"))["api_key"])')"
test -n "$API_KEY"
echo "namespace=${NS} key=${API_KEY:0:8}…"

kubectl get ns "${NS}" >/dev/null
kubectl -n "${NS}" get resourcequota >/dev/null

echo "== tenant workload =="
api_auth DELETE "/workloads/${NAME}" -o /dev/null -w "%{http_code}\n" || true
api_auth POST /workloads -d "{\"name\":\"${NAME}\",\"image\":\"${IMAGE}\",\"port\":${PORT},\"replicas\":1,\"apply\":true}" \
  | tee /tmp/openyard-tenant-create.json
python3 -c 'import json; d=json.load(open("/tmp/openyard-tenant-create.json")); assert d["project"]=="'"${PROJECT}"'"; assert d["namespace"]=="'"${NS}"'"'

echo "== wait ready =="
deadline=$((SECONDS + TIMEOUT_S))
status="deploying"
while (( SECONDS < deadline )); do
  api_auth GET "/workloads/${NAME}/status" | tee /tmp/openyard-tenant-status.json >/dev/null
  status="$(python3 -c 'import json; print(json.load(open("/tmp/openyard-tenant-status.json")).get("status",""))')"
  ready="$(python3 -c 'import json; print(json.load(open("/tmp/openyard-tenant-status.json")).get("ready_replicas",0))')"
  echo "status=${status} ready=${ready}"
  if [[ "$status" == "ready" && "$ready" -ge 1 ]]; then
    break
  fi
  sleep 5
done
if [[ "$status" != "ready" ]]; then
  dump_debug
  exit 1
fi

echo "== ingress in tenant ns =="
kubectl -n "${NS}" get ingress "${NAME}" -o jsonpath='{.spec.rules[0].host}{"\n"}' | tee /tmp/openyard-tenant-ingress.txt
grep -qx "${NAME}.openyard.local" /tmp/openyard-tenant-ingress.txt

echo "== http via ingress =="
deadline=$((SECONDS + TIMEOUT_S))
code="000"
while (( SECONDS < deadline )); do
  code="$(curl -sS -o /tmp/openyard-tenant-http.out -w "%{http_code}" -H "Host: ${NAME}.openyard.local" "http://127.0.0.1:8080/" || true)"
  echo "http=${code}"
  [[ "$code" == "200" ]] && break
  sleep 3
done
if [[ "$code" != "200" ]]; then
  cat /tmp/openyard-tenant-http.out
  dump_debug
  exit 1
fi

echo "== cleanup =="
api_auth DELETE "/workloads/${NAME}" -o /dev/null || true
api_auth DELETE "/projects/${PROJECT}" -o /dev/null || true
echo "e2e tenant OK"

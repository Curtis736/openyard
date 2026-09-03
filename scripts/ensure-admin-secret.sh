#!/usr/bin/env bash
# Crée ou met à jour le Secret openyard-control (OPENYARD_API_KEY).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${OPENYARD_NAMESPACE:-openyard}"
KEY="${OPENYARD_API_KEY:-${KEY:-}}"

kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

if [[ -z "$KEY" ]]; then
  echo "OPENYARD_API_KEY vide → Secret avec clé vide (auth admin off)."
  KEY=""
else
  echo "OPENYARD_API_KEY défini → Secret mis à jour."
fi

kubectl -n "$NS" create secret generic openyard-control \
  --from-literal=OPENYARD_API_KEY="$KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret $NS/openyard-control OK"

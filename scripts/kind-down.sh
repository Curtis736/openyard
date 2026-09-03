#!/usr/bin/env bash
set -euo pipefail

CLUSTER="${CLUSTER:-openyard}"

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind delete cluster --name "$CLUSTER"
  echo "Cluster kind/${CLUSTER} détruit."
else
  echo "Aucun cluster ${CLUSTER}."
fi

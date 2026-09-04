#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
kubectl apply -k k8s/observability
kubectl -n openyard-obs rollout status deploy/prometheus --timeout=180s
kubectl -n openyard-obs rollout status deploy/grafana --timeout=180s
echo "Prometheus : http://prometheus.openyard.local (Host /etc/hosts → 127.0.0.1:8080)"
echo "Grafana    : http://grafana.openyard.local  (anon Viewer / admin:openyard)"

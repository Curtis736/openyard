#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="${CLUSTER:-openyard}"
IMAGE_TAG="${IMAGE_TAG:-openyard:local}"

cd "$ROOT"

if ! command -v kind >/dev/null; then
  echo "kind est requis" >&2
  exit 1
fi

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER" --config kind-config.yaml
fi

kubectl cluster-info --context "kind-${CLUSTER}" >/dev/null

if ! kubectl get ns ingress-nginx >/dev/null 2>&1; then
  kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/kind/deploy.yaml
  kubectl -n ingress-nginx wait --for=condition=ready pod \
    -l app.kubernetes.io/component=controller --timeout=180s
fi

docker build -t "$IMAGE_TAG" .
kind load docker-image "$IMAGE_TAG" --name "$CLUSTER"

kubectl apply -k k8s/overlays/kind
kubectl -n openyard rollout status deployment/openyard-control --timeout=120s
kubectl -n openyard rollout status deployment/demo-web --timeout=120s
kubectl -n openyard rollout status deployment/demo-echo --timeout=120s

echo
echo "Pods :"
kubectl -n openyard get pods -o wide
echo
echo "Services :"
kubectl -n openyard get svc
echo
echo "API : curl -s -H 'Host: openyard.local' http://127.0.0.1:8080/health"
echo "Docs : http://openyard.local:8080/docs  (ajouter 127.0.0.1 openyard.local dans /etc/hosts)"

# OpenYard

[![CI](https://github.com/Curtis736/openyard/actions/workflows/ci.yml/badge.svg)](https://github.com/Curtis736/openyard/actions)
[![Licence](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

Petit **cloud open source** local : on enregistre une image Docker, l’API
produit le Deployment Kubernetes qui la fait tourner en **pods**. Le plan de
contrôle, deux charges de démo et l’ingress tournent sur **kind** — sans
facture cloud.

## Idée

Un cloud managé cache le passage conteneur → orchestration. OpenYard le rend
lisible :

1. `POST /workloads` avec une image et un nombre de réplicas
2. `GET /workloads/{name}/manifest` renvoie Deployment + Service
3. Sur kind, le même modèle est déjà appliqué pour le plan de contrôle et deux
   tenants de démo (`demo-web`, `demo-echo`)

## API

| Méthode | Chemin | Description |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/metrics` | Prometheus |
| GET | `/stats` | Nombre de workloads et pods désirés |
| POST | `/workloads` | Enregistrer une charge (image Docker) |
| GET | `/workloads` | Lister |
| GET | `/workloads/{name}` | Détail |
| GET | `/workloads/{name}/manifest` | YAML Deployment + Service |
| DELETE | `/workloads/{name}` | Retirer |

OpenAPI : `/docs`.

## Local (API seule)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest -q
uvicorn app.main:app --reload
```

```bash
curl -s -X POST http://127.0.0.1:8000/workloads \
  -H 'content-type: application/json' \
  -d '{"name":"edge-api","image":"nginxinc/nginx-unprivileged:1.27-alpine","replicas":2,"port":8080}'
curl -s http://127.0.0.1:8000/workloads/edge-api/manifest
```

## Docker

Image multi-stage, utilisateur `appuser` (uid 10001), filesystem lecture seule.

```bash
docker compose up --build
curl -s http://127.0.0.1:8000/health
```

Image GHCR :

```
ghcr.io/curtis736/openyard:latest
```

## Kubernetes (kind)

```
k8s/base/                 # plan de contrôle + pods de démo
k8s/overlays/kind/        # image locale openyard:local
kind-config.yaml
scripts/kind-up.sh
scripts/kind-down.sh
```

```bash
chmod +x scripts/*.sh
./scripts/kind-up.sh

curl -s -H 'Host: openyard.local' http://127.0.0.1:8080/health
kubectl -n openyard get pods
```

`/etc/hosts` : `127.0.0.1 openyard.local`

Détruire : `./scripts/kind-down.sh`

## Sécurité des pods

Plan de contrôle et charges de démo : non-root, `drop ALL`, seccomp
`RuntimeDefault`, token de service account non monté. NetworkPolicy sur le
plan de contrôle (ingress depuis `ingress-nginx` uniquement).

## CI

GitHub Actions : Ruff, Pytest, Kustomize + kubeconform, build Docker, Trivy,
push GHCR sur `main`.

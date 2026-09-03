# OpenYard

[![CI](https://github.com/Curtis736/openyard/actions/workflows/ci.yml/badge.svg)](https://github.com/Curtis736/openyard/actions)
[![Licence](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Open cloud** open source : site web + console + API. On enregistre une image
Docker, le control plane produit le Deployment Kubernetes et peut l’**appliquer**
sur le cluster pour faire tourner des **pods**. Plan de contrôle, charges de
démo, RBAC et quotas tournent sur **kind** — sans facture cloud.

## Idée

Un cloud managé cache le passage conteneur → orchestration. OpenYard le rend
lisible :

1. Console `/console` (ou `POST /workloads`) avec une image et des réplicas
2. `GET /workloads/{name}/manifest` renvoie Deployment + Service
3. Apply depuis la console (ou `POST .../apply`) crée les pods via l’API
   Kubernetes, avec le ServiceAccount du plan de contrôle
4. Suivi du statut : `readyReplicas` du Deployment

## Site & console

| URL | Contenu |
| --- | --- |
| `/` | Landing OpenYard |
| `/console` | UI pour créer / apply / status / YAML / supprimer |
| `/docs` | OpenAPI |
| `/assets/*` | CSS / JS |

Le dossier `web/` est embarqué dans l’image Docker : sur kind,
`http://openyard.local/` sert le site.

## API

| Méthode | Chemin | Description |
| --- | --- | --- |
| GET | `/health` | Liveness + mode cluster |
| GET | `/metrics` | Prometheus |
| GET | `/stats` | Workloads / pods désirés / pods prêts |
| POST | `/workloads` | Enregistrer (`apply: true` optionnel) |
| GET | `/workloads` | Lister |
| GET | `/workloads/{name}` | Détail |
| POST | `/workloads/{name}/apply` | Appliquer sur le cluster |
| GET | `/workloads/{name}/status` | Statut pods (readyReplicas) |
| GET | `/workloads/{name}/manifest` | YAML Deployment + Service |
| DELETE | `/workloads/{name}` | Retirer (et supprimer du cluster si appliqué) |

## Local (API + site)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
make lint test
make run
```

Ouvre http://127.0.0.1:8000/ puis http://127.0.0.1:8000/console

```bash
curl -s -X POST http://127.0.0.1:8000/workloads \
  -H 'content-type: application/json' \
  -d '{"name":"edge-api","image":"nginxinc/nginx-unprivileged:1.27-alpine","replicas":2,"port":8080}'
curl -s http://127.0.0.1:8000/workloads/edge-api/manifest
```

Sans kubeconfig, `/apply` répond `503` — normal hors cluster.

## Docker

```bash
make compose
# ou
docker compose up --build
```

Image GHCR : `ghcr.io/curtis736/openyard:latest`

## Kubernetes (kind)

```
k8s/base/           # plan de contrôle, RBAC, quotas, PDB, démos
k8s/overlays/kind/  # image locale openyard:local
scripts/kind-up.sh
```

```bash
make up
# site : http://openyard.local/  (Host header ou /etc/hosts)
curl -s -H 'Host: openyard.local' http://127.0.0.1:8080/health
kubectl -n openyard get pods,sa,role,resourcequota
```

`/etc/hosts` : `127.0.0.1 openyard.local`

Appliquer une charge depuis l’API (dans le cluster) :

```bash
curl -s -X POST http://127.0.0.1:8080/workloads \
  -H 'Host: openyard.local' -H 'content-type: application/json' \
  -d '{"name":"edge","image":"hashicorp/http-echo:1.0","port":5678,"apply":true}'
kubectl -n openyard get deploy,pods -l openyard.io/managed=true
```

Détruire : `make down`

## Sécurité

- Pods non-root, `drop ALL`, seccomp `RuntimeDefault`
- Role limité au namespace `openyard` (deployments, services, pods)
- ResourceQuota + LimitRange
- NetworkPolicy : ingress depuis `ingress-nginx`, egress DNS + API Kubernetes
- Token de ServiceAccount monté uniquement sur le plan de contrôle (pour apply)

## CI

GitHub Actions : Ruff, Pytest, Kustomize + kubeconform, build Docker, Trivy,
push GHCR sur `main`.

## Make

| Cible | Action |
| --- | --- |
| `make lint` / `make test` | Qualité |
| `make run` | API + site local sans cluster |
| `make up` / `make down` | kind |
| `make compose` | Docker Compose |
| `make manifests` | `kustomize build` |

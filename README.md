# OpenYard

[![CI](https://github.com/Curtis736/openyard/actions/workflows/ci.yml/badge.svg)](https://github.com/Curtis736/openyard/actions)
[![Licence](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Open cloud** open source : site web + console + API.

- **Workloads** : image Docker → Deployment Kubernetes → pods
- **VM Linux** : Ubuntu 22.04 / 24.04 (driver `sim` ou **Multipass**)

Plan de contrôle, démos, RBAC et quotas tournent sur **kind** — sans facture cloud.

## Idée

Un cloud managé cache le passage conteneur → orchestration (et IaaS). OpenYard
les rend lisibles :

1. Console `/console` : onglet Workloads ou **VM Linux**
2. Workloads : manifest Deployment + Service, apply cluster, statut pods
3. VM Linux Ubuntu : launch / start / stop / delete (sim ou Multipass)

## Site & console

| URL | Contenu |
| --- | --- |
| `/` | Landing OpenYard |
| `/console` | Workloads + VM Linux (Ubuntu) |
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
| GET | `/compute/images` | Catalogue VM Linux (Ubuntu) |
| POST | `/instances` | Lancer une VM Linux |
| GET | `/instances` | Lister |
| GET | `/instances/{name}/status` | Rafraîchir le statut |
| POST | `/instances/{name}/stop` | Arrêter |
| POST | `/instances/{name}/start` | Démarrer |
| DELETE | `/instances/{name}` | Supprimer |

Images acceptées : `ubuntu-22.04`, `ubuntu-24.04`, `ubuntu-lts` (Linux uniquement).

### Compute drivers

| `OPENYARD_COMPUTE` | Comportement |
| --- | --- |
| `auto` (défaut) | Multipass si installé, sinon `sim` |
| `sim` | VM Linux Ubuntu simulées (IP `10.88.0.x`) |
| `multipass` | Vraies VM Ubuntu via [Multipass](https://canonical.com/multipass) |
| `off` | Compute désactivé |

```bash
# Vraies VM Linux (mot de passe admin Homebrew) :
brew install --cask multipass
OPENYARD_COMPUTE=multipass make run
```

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

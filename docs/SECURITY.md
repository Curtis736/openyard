# Sécurité OpenYard

OpenYard est un laboratoire pédagogique : isolement soft, pas un cloud
de production. Ce document décrit les contrôles présents et les limites.

## Contrôles

- Pods workloads : non-root, `drop ALL`, seccomp, read-only root
- RBAC plan de contrôle : ClusterRole pour namespaces `oy-*`
- NetworkPolicy (base) : ingress depuis `ingress-nginx`
- Auth optionnelle : Secret `OPENYARD_API_KEY` + clés projet `oy_…`
- Allowlist d’images + refus de `:latest`

## Limites assumées

- Clés projet en clair dans SQLite (pas de KMS)
- Signup `POST /projects` ouvert (rate-limit absent)
- `/metrics` et `/docs` publics
- Overlay kind désactive la NetworkPolicy (hostPort ingress)
- Pas de NetworkPolicy par tenant

## Signaler un problème

Ouvre une issue GitHub privée ou un PR décrivant le scénario.
Pas de bug bounty — corrections bienvenues.

## Secrets

| Secret | Usage |
| --- | --- |
| `OPENYARD_API_KEY` (env / K8s Secret) | Admin global |
| `oy_…` (SQLite) | Scope projet |

Ne jamais committer une vraie clé. Le manifeste de base ship une clé vide.

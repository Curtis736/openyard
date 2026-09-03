# Sécurité OpenYard

OpenYard est un laboratoire pédagogique : isolement soft, pas un cloud
de production. Ce document décrit les contrôles présents et les limites.

## Contrôles

- Pods workloads : non-root, `drop ALL`, seccomp, read-only root
- RBAC plan de contrôle : ClusterRole pour namespaces `oy-*`
- NetworkPolicy (base) : ingress depuis `ingress-nginx`
- Auth optionnelle : Secret `OPENYARD_API_KEY` + clés projet `oy_…`
- Allowlist d’images + refus de `:latest`

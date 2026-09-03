# Architecture OpenYard

OpenYard est un **mini plan de contrôle** : API FastAPI + SQLite +
drivers Kubernetes / Multipass, exposé via une console web française.

## Vue d’ensemble

```mermaid
flowchart LR
  Browser[Navigateur / curl]
  API[FastAPI control-plane]
  DB[(SQLite OPENYARD_DB)]
  K8s[Kubernetes API]
  MP[Multipass]

  Browser -->|HTTP Host openyard.local| API
  API --> DB
  API -->|workloads apply| K8s
  API -->|instances| MP
```

## Multi-tenant

```mermaid
flowchart TB
  POST[POST /projects]
  Store[SQLite project + oy_ key]
  NS[Namespace oy-name]
  RQ[ResourceQuota]

  POST --> Store
  POST --> NS
  POST --> RQ
  Store -->|X-API-Key| APIScope[Workloads / instances scopés]
```

- Projet `default` → namespace `openyard` (anonyme si pas d’admin key)
- Autres projets → `oy-{name}` + clé `oy_…`

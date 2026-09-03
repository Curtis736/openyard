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

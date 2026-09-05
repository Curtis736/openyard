# Console `/console`

SPA légère (HTML/CSS/JS) branchée sur l’API OpenYard.

## Onglets

| Onglet | Actions |
| --- | --- |
| Projets | Créer tenant, quotas, récupérer `oy_…` |
| Workloads | Presets, apply, statut, manifest YAML |
| VM Linux | Catalogue Ubuntu, launch/stop/start |

La clé API est stockée en `localStorage` (démo locale uniquement).

## Wireframe

```mermaid
flowchart TB
  subgraph console [Cloud Console]
    Nav[API key + projet]
    Tabs[Projets | Workloads | VM]
    Main[Formulaires + tableaux]
    Poll[Poll statut]
  end
  Nav --> Tabs --> Main
  Poll --> Main
```

## Observabilité workload

Sur chaque ligne workload :

- **Events** → `GET /workloads/{name}/events`
- **Logs** → `GET /workloads/{name}/logs?tail=200`

Affichés dans le modal existant (texte brut).

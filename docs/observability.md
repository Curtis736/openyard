# Observabilité

Stack légère dans le namespace `openyard-obs` :

| Composant | URL (kind) | Rôle |
| --- | --- | --- |
| Prometheus | `http://prometheus.openyard.local` | scrape `/metrics` OpenYard |
| Grafana | `http://grafana.openyard.local` | dashboard OpenYard (anon Viewer) |

```bash
make up    # inclut obs-up
# ou
make obs
```

Métriques scrapées : `openyard_up`, `openyard_workloads`, `openyard_pods_*`,
`openyard_instances*`, `openyard_projects`.

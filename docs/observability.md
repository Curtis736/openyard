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

## Vérifier le scrape

```bash
curl -s -H 'Host: prometheus.openyard.local' \
  'http://127.0.0.1:8080/api/v1/targets' | head
curl -s -H 'Host: openyard.local' http://127.0.0.1:8080/metrics | head
```

## Compte Grafana

- Anonyme : Viewer
- Admin labo : `admin` / `openyard`

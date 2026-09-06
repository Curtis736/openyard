# Chart OpenYard

Packaging GitOps du plan de contrôle.

## Values clés

| Key | Description |
| --- | --- |
| `image.repository` / `image.tag` | Image control-plane |
| `ingress.host` | Host Ingress + `OPENYARD_INGRESS_DOMAIN` |
| `persistence.*` | PVC SQLite `/data` |
| `apiKey` | `OPENYARD_API_KEY` (Secret) |

```bash
helm template openyard charts/openyard | kubeconform -strict -summary
helm upgrade --install openyard charts/openyard -n openyard --create-namespace \
  --set image.tag=1.0.0 --set ingress.host=openyard.local --set apiKey=''
```

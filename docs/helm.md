# Helm / GitOps

Chart : `charts/openyard`

Valeurs principales : `image`, `ingress.host`, `persistence`, `apiKey`.

```bash
make helm
helm upgrade --install openyard ./charts/openyard -n openyard --create-namespace \
  --set image.tag=sha-$(git rev-parse --short HEAD) \
  --set ingress.host=openyard.local
```

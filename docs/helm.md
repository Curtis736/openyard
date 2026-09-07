# Helm / GitOps

Chart : `charts/openyard`

Valeurs principales : `image`, `ingress.host`, `persistence`, `apiKey`.

```bash
make helm
helm upgrade --install openyard ./charts/openyard -n openyard --create-namespace \
  --set image.tag=sha-$(git rev-parse --short HEAD) \
  --set ingress.host=openyard.local
```

## Exemple GitOps

```yaml
# values-prod.yaml
image:
  tag: 1.0.0
ingress:
  host: openyard.example.com
persistence:
  size: 5Gi
apiKey: ""
```

<!-- spaced 65 -->

<!-- spaced 66 -->

<!-- spaced 67 -->

<!-- spaced 68 -->

<!-- spaced 69 -->

<!-- spaced 70 -->

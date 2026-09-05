# Tests e2e (kind)

| Script | Couverture |
| --- | --- |
| `scripts/e2e-kind.sh` | projet `default` / ns `openyard` |
| `scripts/e2e-tenant.sh` | `POST /projects` → ns `oy-*` + `X-API-Key` |

Prérequis : `make up` (ingress + control-plane).

```bash
make e2e
make e2e-tenant
```

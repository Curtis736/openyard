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

## Variables

| Var | Défaut | Rôle |
| --- | --- | --- |
| `PROJECT` | `e2etenant` | nom projet → ns `oy-$PROJECT` |
| `NAME` | `tenant-web` / `e2e-web` | workload |
| `BASE_URL` | `http://127.0.0.1:8080` | entrée ingress |
| `TIMEOUT_S` | `180` | timeouts |

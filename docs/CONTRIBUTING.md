# Contribuer

Merci d’améliorer OpenYard. Préfère des PR petites et testées.

## Dev local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
make lint test
make run
```

Console : http://127.0.0.1:8000/console

## Checklist PR

- [ ] `make lint` et `make test` OK
- [ ] Manifests : `make manifests` / kubeconform si YAML K8s
- [ ] Doc à jour si comportement user-facing
- [ ] Pas de secret réel commité

## Observabilité

Après `make up`, Grafana (anon Viewer) expose le dashboard **OpenYard**.

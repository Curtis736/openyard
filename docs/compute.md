# Compute IaaS (VM Linux)

## Quotas

Chaque projet a `instances_quota` (défaut 5). Au-delà → HTTP 409.

## SSH / cloud-init (Multipass)

- Champ API / console : `ssh_authorized_key`
- Ou env `OPENYARD_SSH_AUTHORIZED_KEY`
- Multipass : `multipass launch … --cloud-init <file>`

```bash
OPENYARD_COMPUTE=multipass OPENYARD_SSH_AUTHORIZED_KEY="$(cat ~/.ssh/id_ed25519.pub)" make run
```

# Laptop Deploy Checklist (192.168.4.40 — the always-on home server)

Quick reference for the laptop. Full runbook: `docs/02` §13.4.

## One-time setup

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into existing clone + git pull
cd Sentinel

# .env (gitignored) — from docs/02 §13.4:
#   SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434   (native Ollama, same host)
#   SENTINEL_PROJECTS_DIR=Z:\                        (SMB share from the desktop)
#   SENTINEL_PIHOLE_HOST=http://192.168.4.40:8053    (System page, optional)
#   SENTINEL_PIHOLE_API_TOKEN=<v6 token>             (optional, read-only)
#   PIHOLE_WEBPASSWORD=<Pi-hole admin password>      (compose profile)

net use Z: \\192.168.4.28\projects /user:james\j <pw> /persistent:yes
```

## Daily operations

```powershell
git pull                                    # update (then rebuild: docker compose up -d --build)
docker compose --profile pihole up -d       # start everything incl. Pi-hole (network DNS!)
docker compose up -d --build                # after a git pull with code changes
docker compose exec backend sentinel index --all   # re-index new/changed repos on the share
```

- Dashboard: `http://192.168.4.40:8080` · System page: `/system`
- Pi-hole admin: `http://192.168.4.40:8053`

## Rules of thumb

- **Never stop Docker wholesale** — Pi-hole is the network's DNS; stopping it
  kills internet for every device until it's back.
- **Never start Pi-hole from Docker Desktop's UI** — it ignores compose env/
  volumes and resets the password. Always `docker compose --profile pihole up -d`.
- After moving the Sentinel folder on disk: the compose volumes are relative
  (`./data/...`) — the stack will use the new location's (empty) data dirs.
  Re-run `sentinel index --all` and re-set the Pi-hole password once.
- Password reset if needed: `docker compose exec pihole pihole setpassword`

## Known issues (see docs/02 §13.4 troubleshooting table)

- `net use` error 67 → desktop firewall SMB-In Private rule was off (now enabled).
- `/frontend: not found` build error → fixed in `.dockerignore` (v1.12.1),
  regression-tested.
- Stale containers after `git pull` → `docker compose up -d --build`.

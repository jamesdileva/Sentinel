# Laptop Deploy Checklist (192.168.4.40 — the always-on home server)

Quick reference for the laptop. Full runbook: `docs/02` §13.4.

## One-time setup

```powershell
git clone https://github.com/jamesdileva/Sentinel.git   # or cd into existing clone + git pull
cd Sentinel

# .env (gitignored) — from docs/02 §13.4:
#   SENTINEL_OLLAMA_HOST=http://192.168.4.40:11434     (native Ollama, same host)
#   SENTINEL_GITHUB_TOKEN=<read-only PAT>              (repo auto-sync, Sprint 12.1)
#   SENTINEL_PROJECTS_DIR=C:\Users\james\projects       (local clone target)
#   SENTINEL_PIHOLE_HOST=http://192.168.4.40:8053       (System page, optional)
#   SENTINEL_PIHOLE_PASSWORD=<Pi-hole web admin pw>     (System page, optional)
#   PIHOLE_WEBPASSWORD=<Pi-hole admin password>         (compose profile)

docker compose --profile pihole up -d --build
docker compose exec backend sentinel sync   # one immediate clone/pull pass from GitHub
docker compose exec backend sentinel index --all
```

Repos are cloned under `owner/name` inside the projects dir; the `repo-sync`
beat keeps them current every 15 minutes (`SENTINEL_SYNC_INTERVAL_MINUTES`).
Repos that exist only locally (no GitHub `origin`) are not synced — push them
to GitHub to have the laptop pick them up.

Since v1.14, each sync pass also auto-queues knowledge (RAG) indexing for
projects that have unembedded files, as long as Ollama is up — the Chat tab
gets data with no extra step (`sentinel sync` prints the queued count).

## Daily operations

```powershell
git pull                                    # update (then rebuild: docker compose up -d --build)
docker compose --profile pihole up -d       # start everything incl. Pi-hole (network DNS!)
docker compose up -d --build                # after a git pull with code changes
docker compose exec backend sentinel sync   # immediate repo sync if you don't want to wait
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

- `/frontend: not found` build error → fixed in `.dockerignore` (v1.12.1),
  regression-tested.
- Stale containers after `git pull` → `docker compose up -d --build`.
- System page Pi-hole *authentication failed* → check `SENTINEL_PIHOLE_PASSWORD`
  matches the web admin password (v6 session auth; the old API token is gone).

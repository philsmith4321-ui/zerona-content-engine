# CLAUDE.md

## Deployment

- **DigitalOcean droplet:** 159.89.91.177 (SSH: `ssh root@159.89.91.177`)
- **App code on server:** `/root/zerona-content-engine`
- **Stack:** Docker Compose (single `app` container: FastAPI + Uvicorn), nginx on host with self-signed SSL
- **Access:** https://159.89.91.177 (self-signed cert, no basic auth)
- **No git on server** — deploy via SCP then rebuild:
  ```bash
  scp <files> root@159.89.91.177:/root/zerona-content-engine/<path>
  ssh root@159.89.91.177 "cd /root/zerona-content-engine && docker compose up -d --build"
  ```
- **Health check:** `curl -sk https://159.89.91.177/health`
- After any app changes, always deploy to the droplet and rebuild.

## Billing & Authentication Policy
**Effective May 11, 2026** — All Claude Code usage runs through Philip Smith's Claude Max subscription. Never authenticate via `ANTHROPIC_API_KEY` or Console API credits. If `/status` shows API credit billing, stop and run `claude logout` → `claude login` → choose the claude.ai option.

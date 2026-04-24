# Module 1 Deployment Checklist — Email Campaigns

**Last updated:** 2026-04-23
**Target:** VPS at 104.131.74.47 (DigitalOcean droplet)
**Current state:** VPS runs `main` branch via Docker Compose. Module 1 code is on `feature/module-1-campaigns` (not merged, not deployed).

## Production Environment Summary

| Component | Detail |
|-----------|--------|
| Host | 104.131.74.47 |
| App path | `/root/zerona-content-engine` |
| Runtime | Docker container (`python:3.12-slim`) |
| Compose | `docker-compose.yml` — single `app` service |
| Port | 8000 (mapped host:container) |
| Volumes | `./data:/app/data`, `./media:/app/media`, `./prompts:/app/prompts`, `./config:/app/config` |
| Database | SQLite at `data/content.db` (bind-mounted, persists across rebuilds) |
| Env | `.env` file on host, loaded via `env_file` in compose |
| Git remote | `git@github.com:philsmith4321-ui/zerona-content-engine.git` |
| Branch deployed | `main` |
| Restart policy | `unless-stopped` |

---

## BLOCKER: HTTPS Required Before Real Patient Data

The VPS currently serves over HTTP. Module 1 handles patient names, emails, phone numbers, visit history, and health information. **This data MUST NOT be transmitted over unencrypted HTTP.**

Deployment is split into three stages:

| Stage | What | Transport | Data |
|-------|------|-----------|------|
| **A** | Deploy Module 1, smoke-test all features | HTTP (current) | Fake/test data only |
| **B** | Set up HTTPS via Caddy reverse proxy | HTTPS | Still fake data |
| **C** | Import real patient CSV, begin real campaigns | HTTPS (verified) | Real patient data |

**Do not proceed past Stage A until HTTPS is in place.**

Stage B requires a domain name pointed at the VPS (e.g., `app.whitehousechiropractic.com`). This domain has not been established yet — Chris needs to decide and create the DNS A record. See HTTPS setup runbook (to be written).

> **Open question for Chris:** What domain should the app live on? Example: `app.whitehousechiropractic.com`. We need this before we can set up HTTPS.

---

## Phase 1: Pre-Deployment (Do Before Touching the VPS)

### 1.1 Mailgun Account Setup

Chris needs to complete these steps in the Mailgun dashboard:

- [ ] Create Mailgun account at https://www.mailgun.com (Flex plan: 1,000 free emails/month)
- [ ] Add sending domain: `mail.whitehousechiropractic.com` (subdomain recommended over root domain)
- [ ] Note the following credentials from Mailgun dashboard:
  - **Private API Key:** Settings > API Security > Private API key
  - **Webhook Signing Key:** Settings > API Security > HTTP Webhook Signing Key

### 1.2 DNS Records

Chris (or his DNS provider) needs to add these records for `mail.whitehousechiropractic.com`. The exact values come from the Mailgun dashboard after adding the domain — the ones below are format examples.

**SPF Record:**

| Type | Host | Value |
|------|------|-------|
| TXT | `mail.whitehousechiropractic.com` | `v=spf1 include:mailgun.org ~all` |

**DKIM Records (2 records — exact values from Mailgun):**

| Type | Host | Value |
|------|------|-------|
| TXT | `smtp._domainkey.mail.whitehousechiropractic.com` | *(long RSA key provided by Mailgun)* |

**DMARC Record:**

| Type | Host | Value |
|------|------|-------|
| TXT | `_dmarc.mail.whitehousechiropractic.com` | `v=DMARC1; p=none; rua=mailto:dmarc@whitehousechiropractic.com` |

> Start with `p=none` to monitor. Change to `p=quarantine` after confirming deliverability.

**MX Records (for bounce processing):**

| Type | Host | Priority | Value |
|------|------|----------|-------|
| MX | `mail.whitehousechiropractic.com` | 10 | `mxa.mailgun.org` |
| MX | `mail.whitehousechiropractic.com` | 10 | `mxb.mailgun.org` |

**CNAME Record (for click/open tracking):**

| Type | Host | Value |
|------|------|-------|
| CNAME | `email.mail.whitehousechiropractic.com` | `mailgun.org` |

- [ ] All DNS records added
- [ ] Click "Verify DNS Settings" in Mailgun dashboard — wait for green checkmarks (can take up to 48 hours for propagation)

### 1.3 Mailgun Webhook Configuration

In Mailgun dashboard: Sending > Webhooks

- [ ] Add webhook URL: `http://104.131.74.47:8000/webhooks/mailgun`
- [ ] Select ALL event types: Delivered, Opened, Clicked, Bounced/Failed, Complained, Unsubscribed

> Note: This uses HTTP, not HTTPS. If HTTPS is set up on the VPS later, update the webhook URL. Mailgun verifies webhooks via HMAC signature regardless of transport.

### 1.4 Environment Variables

These must be added to `/root/zerona-content-engine/.env` on the VPS before deploying:

```
# Mailgun (add these lines to the existing .env file)
MAILGUN_API_KEY=key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MAILGUN_DOMAIN=mail.whitehousechiropractic.com
MAILGUN_FROM_EMAIL=hello@mail.whitehousechiropractic.com
MAILGUN_FROM_NAME=White House Chiropractic
MAILGUN_WEBHOOK_SIGNING_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- [ ] Environment variables added to `.env` on VPS (with real values from Mailgun dashboard)

---

## Phase 2: Deployment

### 2.1 Merge Module 1 to Main (Local)

Module 1 is on `feature/module-1-campaigns` (14 commits ahead of `main`). Module 2 is on `feature/module-2-ghl-referrals` which includes Module 1. We need to get Module 1 code onto `main` without Module 2.

```bash
# On local machine
cd /Users/philipsmith/zerona-content-engine

# Switch to main and merge Module 1 only
git checkout main
git merge feature/module-1-campaigns --no-ff -m "Merge Module 1: email campaign manager with Mailgun integration"

# Push to GitHub
git push origin main
```

- [ ] Module 1 merged to `main` locally
- [ ] Pushed to GitHub

### 2.2 Back Up Production Data

Back up **both** the database and the media directory. Then copy the backup off the VPS so a disk failure doesn't destroy both the app and the backup.

```bash
# SSH to VPS
ssh root@104.131.74.47

# Create a timestamped backup directory
BACKUP_DIR="/root/backups/before-module1-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Back up the database
cp /root/zerona-content-engine/data/content.db "$BACKUP_DIR/content.db"

# Back up media files (photos, uploads)
cp -r /root/zerona-content-engine/media "$BACKUP_DIR/media"

# Verify backup contents
ls -lh "$BACKUP_DIR/content.db"
ls -lh "$BACKUP_DIR/media/" 2>/dev/null || echo "No media files (empty directory)"

echo "Backup saved to: $BACKUP_DIR"
```

```bash
# FROM YOUR LOCAL MACHINE — copy backup off the VPS
scp -r root@104.131.74.47:"$BACKUP_DIR" ~/zerona-backups/
# Or use the actual path shown in the echo above, e.g.:
# scp -r root@104.131.74.47:/root/backups/before-module1-20260423-143000 ~/zerona-backups/
```

- [ ] Database backed up on VPS
- [ ] Media directory backed up on VPS
- [ ] Backup copied to local machine (off-VPS)

### 2.3 Pull and Rebuild on VPS

```bash
# On VPS
cd /root/zerona-content-engine

# Pull latest main
git pull origin main

# Rebuild the Docker image (installs new deps from requirements.txt)
docker-compose build --no-cache

# Restart the container
docker-compose down && docker-compose up -d

# Verify container is running
docker-compose ps
# Expected: zerona-content-engine_app_1 ... Up ... 0.0.0.0:8000->8000/tcp

# Check logs for startup errors
docker-compose logs --tail=30
# Look for: "Uvicorn running on http://0.0.0.0:8000"
# Look for: migration 002 and 003 applied (first run only)
```

- [ ] `git pull` succeeded
- [ ] Docker image rebuilt
- [ ] Container running
- [ ] No errors in startup logs
- [ ] Migrations 002 and 003 applied (check logs)

---

## Phase 3: Post-Deployment Smoke Tests

Run these from your local machine or any terminal with curl.

### 3.1 Health Check

```bash
curl -s http://104.131.74.47:8000/health
# Expected: {"status":"ok"}
```

- [ ] Health check returns `{"status":"ok"}`

### 3.2 Login Page Loads

```bash
curl -s -o /dev/null -w "%{http_code}" http://104.131.74.47:8000/login
# Expected: 200
```

- [ ] Login page returns 200

### 3.3 Campaigns Page Loads (Authenticated)

```bash
# Login and save session cookie
curl -s -c /tmp/z-cookies -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "password=YOUR_ADMIN_PASSWORD" \
  "http://104.131.74.47:8000/login" > /dev/null

# Check campaigns page
curl -s -b /tmp/z-cookies \
  -o /dev/null -w "%{http_code}" \
  "http://104.131.74.47:8000/dashboard/campaigns"
# Expected: 200

# Check patients page
curl -s -b /tmp/z-cookies \
  -o /dev/null -w "%{http_code}" \
  "http://104.131.74.47:8000/dashboard/patients"
# Expected: 200

# Clean up
rm /tmp/z-cookies
```

- [ ] Campaigns page returns 200
- [ ] Patients page returns 200

### 3.4 Webhook Endpoint Rejects Unsigned Requests

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"signature":{"token":"fake","timestamp":"0","signature":"bad"}}' \
  http://104.131.74.47:8000/webhooks/mailgun
# Expected: 403 or {"detail":"Invalid webhook signature"} or similar rejection
```

- [ ] Webhook rejects unsigned POST with 403

### 3.5 Diagnostics Page

```bash
# Login first (same as 3.3), then:
curl -s -b /tmp/z-cookies \
  -o /dev/null -w "%{http_code}" \
  "http://104.131.74.47:8000/dashboard/campaigns/diagnostics"
# Expected: 200
```

Open the diagnostics page in a browser to visually verify:
- Mailgun connection status shows connected (or shows config needed if env vars not set yet)
- Database tables exist with correct counts
- Patient tier breakdown shows zeros (no patients imported yet)

- [ ] Diagnostics page loads and shows system status

### 3.6 Data Integrity Verification

Verify that Module 1 migrations did not corrupt or lose any existing production data. Run the row counts **before deployment** (in step 2.2, after backup) and **after deployment** (here). The counts must be identical.

**Before deployment** (run during step 2.2, record the output):

```bash
ssh root@104.131.74.47 'docker exec zerona-content-engine_app_1 python3 -c "
import sqlite3
conn = sqlite3.connect(\"/app/data/content.db\")
for table in [\"content_pieces\", \"content_calendar\", \"system_log\", \"failed_jobs\"]:
    try:
        count = conn.execute(f\"SELECT COUNT(*) FROM {table}\").fetchone()[0]
        print(f\"{table}: {count}\")
    except Exception as e:
        print(f\"{table}: ERROR - {e}\")
conn.close()
"'
```

**After deployment** (run the same command — counts should match):

```bash
ssh root@104.131.74.47 'docker exec zerona-content-engine_app_1 python3 -c "
import sqlite3
conn = sqlite3.connect(\"/app/data/content.db\")
for table in [\"content_pieces\", \"content_calendar\", \"system_log\", \"failed_jobs\"]:
    try:
        count = conn.execute(f\"SELECT COUNT(*) FROM {table}\").fetchone()[0]
        print(f\"{table}: {count}\")
    except Exception as e:
        print(f\"{table}: ERROR - {e}\")
conn.close()
"'
```

- [ ] Pre-deployment row counts recorded
- [ ] Post-deployment row counts match exactly (content_pieces, content_calendar, system_log, failed_jobs)

### 3.7 Existing Features Still Work

Verify the pre-Module-1 features are unbroken:

```bash
# Dashboard loads
curl -s -b /tmp/z-cookies \
  -o /dev/null -w "%{http_code}" \
  "http://104.131.74.47:8000/dashboard"
# Expected: 200

# Content review loads
curl -s -b /tmp/z-cookies \
  -o /dev/null -w "%{http_code}" \
  "http://104.131.74.47:8000/dashboard/content"
# Expected: 200
```

- [ ] Main dashboard loads
- [ ] Existing content/social features work

---

## Phase 4: First Real Send Verification

Only proceed after DNS is verified green in Mailgun dashboard.

### 4.1 Send Test Email

In the browser, go to the campaigns page:
1. Create a new campaign (use any template)
2. Generate AI copy (or write manually)
3. Use the "Test Send" form — enter your own email address
4. Click Send Test

- [ ] Test email arrives in your inbox
- [ ] Email content renders correctly (merge tags show sample values like "Sarah")
- [ ] From address shows `White House Chiropractic` / configured from_email
- [ ] No spam folder placement (check headers for SPF/DKIM pass)

### 4.2 Verify Webhook Fires Back

After opening the test email:

```bash
# Login and check diagnostics
curl -s -c /tmp/z-cookies -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "password=YOUR_ADMIN_PASSWORD" \
  "http://104.131.74.47:8000/login" > /dev/null

# Check container logs for webhook events
ssh root@104.131.74.47 'docker-compose -f /root/zerona-content-engine/docker-compose.yml logs --tail=50 | grep -i "webhook\|delivered\|opened"'
```

Also check the diagnostics page — "Recent Webhook Events" section should show `delivered` and `opened` events.

- [ ] `delivered` event received from Mailgun
- [ ] `opened` event received after opening email
- [ ] Events visible in diagnostics page

### 4.3 Verify Database Recorded Events

```bash
ssh root@104.131.74.47 'docker exec zerona-content-engine_app_1 python3 -c "
from app.database import get_db
conn = get_db()
events = conn.execute(\"SELECT event_type, recipient_email, timestamp FROM campaign_events ORDER BY id DESC LIMIT 5\").fetchall()
for e in events:
    print(f\"{e[0]:15s} {e[1]:30s} {e[2]}\")
conn.close()
"'
```

- [ ] Campaign events stored in database with correct types and timestamps

---

## Phase 5: Rollback Procedure

If deployment breaks the existing site:

### Quick Rollback (< 2 minutes)

```bash
ssh root@104.131.74.47

cd /root/zerona-content-engine

# Revert to previous commit
git checkout main
git reset --hard c80be0c   # The pre-Module-1 commit hash

# Restore database from backup (use the actual backup dir created in step 2.2)
BACKUP_DIR="/root/backups/before-module1-XXXXXXXX-XXXXXX"  # Use actual timestamp
cp "$BACKUP_DIR/content.db" data/content.db
cp -r "$BACKUP_DIR/media" ./media

# Rebuild and restart
docker-compose build --no-cache && docker-compose down && docker-compose up -d

# Verify
curl -s http://104.131.74.47:8000/health
```

### If Git Reset Isn't Enough

```bash
# Nuclear option: rebuild from known good state
cd /root/zerona-content-engine
git fetch origin
git checkout main
git reset --hard origin/main~1  # Go back one commit before the merge
docker-compose build --no-cache && docker-compose down && docker-compose up -d
```

### Post-Rollback

- [ ] Health check passes
- [ ] Dashboard loads
- [ ] Existing content features work
- [ ] Inform team that Module 1 deployment was reverted and why

---

## Notes

- **HTTPS:** See the BLOCKER section at the top of this document. No real patient data until HTTPS is in place.
- **No process manager:** Docker Compose with `restart: unless-stopped` handles restarts. No systemd/supervisor/pm2 needed.
- **SQLite concurrency:** The app uses WAL mode, which supports concurrent reads. Under high load (many webhook callbacks at once), SQLite may become a bottleneck. This is unlikely at the 7,500-patient scale but worth monitoring.
- **Warmup schedule:** The first campaign from a new Mailgun domain will automatically use warmup (50/100/250/500/remaining over 5 days). The admin can bypass this per-campaign but will need to understand the deliverability risk.

# Zerona Content Engine — Mailgun Setup Guide

## 1. Create a Mailgun Account

Sign up at https://www.mailgun.com. The Flex plan includes 1,000 free emails/month.

## 2. Add Your Sending Domain

In the Mailgun dashboard, go to **Sending > Domains > Add New Domain**.

Use a subdomain like `mail.whitehousechiropractic.com` (recommended over the root domain).

## 3. DNS Records to Add

After adding the domain, Mailgun will provide these records. Add them in your DNS provider (GoDaddy, Cloudflare, etc.):

### SPF Record
| Type | Host/Name | Value |
|------|-----------|-------|
| TXT | mail.whitehousechiropractic.com | `v=spf1 include:mailgun.org ~all` |

### DKIM Records
Mailgun generates two DKIM records. They look like:

| Type | Host/Name | Value |
|------|-----------|-------|
| TXT | smtp._domainkey.mail.whitehousechiropractic.com | `k=rsa; p=MIGfMA0GCSq...` (long key provided by Mailgun) |

### DMARC Record
| Type | Host/Name | Value |
|------|-----------|-------|
| TXT | _dmarc.mail.whitehousechiropractic.com | `v=DMARC1; p=none; rua=mailto:dmarc@whitehousechiropractic.com` |

> Start with `p=none` to monitor. After confirming deliverability is good, change to `p=quarantine`.

### MX Records (for receiving bounces)
| Type | Host/Name | Priority | Value |
|------|-----------|----------|-------|
| MX | mail.whitehousechiropractic.com | 10 | `mxa.mailgun.org` |
| MX | mail.whitehousechiropractic.com | 10 | `mxb.mailgun.org` |

### CNAME Record (for click/open tracking)
| Type | Host/Name | Value |
|------|-----------|-------|
| CNAME | email.mail.whitehousechiropractic.com | `mailgun.org` |

## 4. Verify Domain

After adding all DNS records, click **Verify DNS Settings** in Mailgun. DNS propagation can take up to 48 hours.

## 5. Get API Keys

In Mailgun dashboard:
- **API Key**: Settings > API Security > Private API key
- **Webhook Signing Key**: Settings > API Security > HTTP Webhook Signing Key

## 6. Configure Webhooks

In Mailgun dashboard, go to **Sending > Webhooks**.

Add a webhook for your server:
- **URL**: `https://your-server-ip:8000/webhooks/mailgun`
- **Events**: Select ALL events (Delivered, Opened, Clicked, Bounced/Failed, Complained, Unsubscribed)

## 7. Set Environment Variables

Add to your `.env` file on the server:

```
MAILGUN_API_KEY=key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MAILGUN_DOMAIN=mail.whitehousechiropractic.com
MAILGUN_FROM_EMAIL=hello@mail.whitehousechiropractic.com
MAILGUN_FROM_NAME=White House Chiropractic
MAILGUN_WEBHOOK_SIGNING_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 8. Domain Warmup

The first campaign from a new domain uses automatic warmup:
- Day 1: 50 emails
- Day 2: 100 emails
- Day 3: 250 emails
- Day 4: 500 emails
- Day 5: Remaining

This protects deliverability. The admin can override this per-campaign but will see a warning.

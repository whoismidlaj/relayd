# Relayd — PRD

## Original problem statement
Build a modern self-hostable email orchestration platform — a central dashboard for managing domains, inboxes, aliases, outbound relay providers, inbound routing, delivery logs, DNS records, mail routing and deliverability. Lightweight, modular, developer-friendly, privacy-focused. Target: self-hosters, devs, indie hackers, agencies.

## User decisions (Feb 2026)
- Auth: **JWT-based custom auth (email + password)**
- Relay scope: **Generic SMTP + Resend wired; SES / Brevo / SMTP2GO config-only**
- DNS verification: **real-time DNS lookups via dnspython**
- Design: **shadcn-like, simple, light + dark mode**
- Deployment: **docker-compose + README**

## User personas
- Self-hosters managing one or two domains
- Indie hackers running transactional email for their SaaS
- Agencies configuring email infra for multiple clients
- Developers experimenting with relay-aware architectures

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB) + PyJWT + bcrypt + dnspython + cryptography + Resend SDK + aiosmtplib
- **Frontend**: React 19 + React Router 7 + Tailwind + Shadcn UI + sonner + lucide-react + axios
- **DB**: MongoDB (collections: users, login_attempts, domains, mailboxes, aliases, relays, delivery_logs)
- **Deploy**: docker-compose (mongo + backend uvicorn + frontend nginx)

## What's been implemented (2026-02-14)
- JWT auth: register / login / me / logout / refresh, brute-force lockout, admin seed
- Domain CRUD + DKIM keypair generation + SPF/DKIM/DMARC/MX/A record generation + live DNS verification with score 0–100
- Mailbox CRUD (bcrypt-hashed password, display name, quota)
- Alias CRUD with multi-destination forwarding, catch-all (`*`), enable/disable toggle
- Relay providers: 5 types (smtp, resend, ses, brevo, smtp2go); priority + default + masked secrets
- Test email send with retry (2 attempts) and failover across providers ordered by priority
- Delivery logs with full attempt trail; retry-from-log; delete-log
- Deliverability dashboard (per-domain SPF/DKIM/DMARC/MX live checks + composite score)
- Stats endpoint feeding the dashboard
- Multi-tenant isolation enforced via `user_id` on every collection
- Dark/light/system theme toggle (next-themes-style with localStorage)
- Docker compose stack (mongo + backend + nginx-served frontend, single port 8080)
- README with quick-start, docker, API reference, roadmap

## Bug fixes (testing agent iteration 1)
- Fixed `locked_until` naive vs aware datetime comparison in brute-force path
- Fixed mailbox/alias/relay create routes returning `_id` ObjectId (FastAPI 500)

## Prioritized backlog
**P0 — must-have for next iteration**
- Inbound SMTP listener + actual mailbox delivery (currently mailbox is "registered" but no IMAP/SMTP daemon)
- Persistent background queue (currently in-request retry loop)
- Wire Amazon SES, Brevo, SMTP2GO (boto3 / brevo SDK / smtp2go HTTP API)

**P1**
- API token issuance for programmatic access
- Webhook events (sent, bounced, opened) — outgoing webhooks per user
- Per-domain default relay binding
- Bounce parsing & reputation tracking
- Self-hosted IMAP inbox storage (Dovecot / Maddy integration)

**P2**
- Spam diagnostics (header forensics, mail-tester-style report)
- Blacklist / RBL monitoring
- Multi-user roles & team workspaces
- Bring-your-own DNS provider auto-publish (Cloudflare, Route53, …)

## Next actions
- Validate frontend end-to-end manually in preview
- Consider P0 work to make the platform actually deliver inbound mail

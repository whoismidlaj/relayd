# MailCtl — Modern Self-Hostable Email Orchestration Platform

> A lightweight, modular, developer-friendly control plane for your email infrastructure.
> Manage domains, DKIM/SPF/DMARC, mailboxes, aliases and outbound relays — all from a clean dashboard.

MailCtl is **not** a Postfix UI, not a cPanel clone, and not a heavy enterprise mail suite.
It's a **relay-aware orchestration platform** built for self-hosters, developers, indie hackers, agencies and privacy-focused users who want a modern terminal-grade control panel for their email infrastructure.

---

## Features (MVP)

- **Auth** — JWT-based email/password authentication with httpOnly cookies + admin seeding + brute-force protection
- **Multi-domain management** — add domains, generate DKIM keypairs, custom selectors & mail hosts
- **Automatic DNS record generation** — SPF, DKIM (RSA-2048), DMARC and MX records ready to copy into your zone
- **Live DNS verification** — real DNS lookups via `dnspython` with deliverability scoring (0–100)
- **Mailbox management** — local-part + domain + bcrypt-hashed password + display name + quota
- **Alias management** — multiple forwarding destinations, enable/disable toggle, **catch-all** support (`*`)
- **Relay providers**
  - Generic SMTP — fully wired (STARTTLS / SSL / plain)
  - Resend — fully wired via official SDK
  - Amazon SES / Brevo / SMTP2GO — config-only stubs in this MVP
- **Priority & failover** — set a default provider; if it fails, the queue retries through the rest by priority
- **Test email send** — full modal with from / to / subject / body and per-relay selection
- **Delivery logs** — every send produces a log entry with attempts, provider response, message-id, error
- **Retry mechanism** — retry failed deliveries from the logs page
- **Deliverability dashboard** — per-domain SPF/DKIM/DMARC/MX live checks + composite score
- **Modern responsive UI** — Shadcn UI + Tailwind, dark/light/system theme, IBM Plex Sans + JetBrains Mono
- **Docker-based self-hostable deployment** — `docker compose up` and you're running

---

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | FastAPI · Motor (async MongoDB) · PyJWT · bcrypt · dnspython · cryptography · Resend SDK |
| Frontend | React 19 · React Router · Tailwind · Shadcn UI · sonner · lucide-react · axios |
| Storage  | MongoDB |
| Deploy   | Docker / docker-compose · nginx (frontend) · uvicorn (backend) |

---

## Quick start (local development)

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

### Frontend
```bash
cd frontend
yarn install
yarn start
```

The admin user is auto-seeded on first run:
```
email:    admin@example.com
password: admin123
```
Change `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `backend/.env` before going to production.

---

## Docker — self-hosted in one command

```bash
docker compose up -d --build
# open http://localhost:8080
```

The stack exposes only the frontend on **port 8080**. Nginx inside the frontend container
proxies `/api/*` to the backend service over the internal `mailctl` network.

### docker-compose env vars
| Var | Default | Purpose |
|-----|---------|---------|
| `JWT_SECRET` | `change-me…` | Sign JWTs. **CHANGE THIS.** |
| `ADMIN_EMAIL` | `admin@example.com` | Initial admin |
| `ADMIN_PASSWORD` | `admin123` | Initial admin password |
| `FRONTEND_URL` | `http://localhost:8080` | CORS allow-list |
| `PUBLIC_BACKEND_URL` | `http://localhost:8080` | Baked into the frontend bundle at build time |

---

## API surface (prefixed with `/api`)

### Auth
- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/refresh`

### Domains
- `GET/POST /domains`, `GET/PATCH/DELETE /domains/{id}`
- `GET /domains/{id}/dns` — generated SPF / DKIM / DMARC / MX records
- `POST /domains/{id}/verify` — live DNS checks + score

### Mailboxes & Aliases
- `GET/POST/PATCH/DELETE /mailboxes[/{id}]`
- `GET/POST/PATCH/DELETE /aliases[/{id}]`

### Relays / Send / Logs
- `GET/POST/PATCH/DELETE /relays[/{id}]`
- `POST /send/test` — send a test email (default + failover, or specific relay)
- `GET /logs`, `POST /logs/{id}/retry`, `DELETE /logs/{id}`

### Deliverability / stats
- `GET /stats` — dashboard counters + recent logs
- `GET /deliverability` — runs live DNS checks over all domains

---

## Product philosophy

MailCtl IS: a modern, relay-aware, self-hostable, modular, lightweight,
developer-friendly and privacy-focused email orchestration platform.

MailCtl IS NOT: a cPanel clone, a traditional hosting panel, a heavy enterprise
mail suite, or an old-school Postfix UI.

---

## Roadmap

- Inbound SMTP relay & built-in MX listener
- Self-hosted IMAP inbox storage
- Webhook events on send / bounce / open
- API tokens for programmatic access
- Reputation monitoring & blacklist checks
- Spam diagnostics & header forensics
- Full wiring for Amazon SES, Brevo, SMTP2GO

---

## License

MIT — fork it, host it, hack on it.

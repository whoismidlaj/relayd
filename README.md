# Relayd — Modern Self-Hostable Email Orchestration Platform

> A lightweight, modular, developer-friendly control plane for your email infrastructure.
> Manage domains, DKIM/SPF/DMARC, mailboxes, aliases and outbound relays — all from a clean dashboard.

Relayd is **not** a Postfix UI, not a cPanel clone, and not a heavy enterprise mail suite.
It's a **relay-aware orchestration platform** built for self-hosters, developers, indie hackers, agencies and privacy-focused users who want a modern terminal-grade control panel for their email infrastructure.

---

## Features (MVP)

- **Auth** — JWT-based email/password authentication & API Keys for developers (`re_...`)
- **Multi-domain management** — add domains, generate DKIM keypairs, custom selectors & mail hosts
- **Automatic DNS record generation** — SPF, DKIM (RSA-2048), DMARC and MX records ready to copy into your zone
- **Live DNS verification** — real DNS lookups via `dnspython` with deliverability scoring (0–100)
- **Mailbox & Alias management** — local-part + domain, bcrypt-hashed passwords, multiple forwarding destinations, **catch-all** support (`*`)
- **Inbound SMTP Listener** — Native `aiosmtpd` controller listening on Port 25 to receive, validate, and store incoming emails for your domains.
- **Persistent Background Worker** — Dedicated worker process for robust, retryable task execution (like sending emails with exponential backoff).
- **Relay providers**
  - Generic SMTP — fully wired (STARTTLS / SSL / plain)
  - Resend — fully wired via official SDK
  - Amazon SES, Brevo, SMTP2GO — fully wired via native REST/Boto3 APIs
- **Priority & failover** — set a default provider; if it fails, the queue retries through the rest by priority
- **Test email send** — full modal with from / to / subject / body and per-relay selection
- **Delivery logs & Inbound Dashboard** — View outbound sending logs and read incoming parsed messages directly in the UI.
- **Deliverability dashboard** — per-domain SPF/DKIM/DMARC/MX live checks + composite score
- **Modern responsive UI** — Shadcn UI + Tailwind, dark/light/system theme, IBM Plex Sans + JetBrains Mono
- **Docker-based self-hostable deployment** — `docker compose up` and you're running

---

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | FastAPI · Motor (async MongoDB) · PyJWT · bcrypt · dnspython · aiosmtpd · Resend SDK |
| Frontend | React 19 · React Router · Tailwind · Shadcn UI · sonner · SWR · lucide-react |
| Storage  | MongoDB (Atlas or local) |
| Deploy   | Docker / docker-compose · nginx (frontend) · uvicorn (server) · python (worker/inbound) |

---

## Quick start (local development)

### Backend Services
Relayd now runs as a multi-process architecture:
```bash
cd backend
pip install -r requirements.txt

# 1. Start the main API server (Port 80)
python server.py

# 2. Start the background worker
python worker.py

# 3. Start the Inbound SMTP listener (Port 25, requires Admin/Root)
python inbound.py
```

### Frontend
```bash
cd frontend
yarn install
# Create .env file with: REACT_APP_BACKEND_URL=http://localhost
yarn start
```

The admin user is auto-seeded on first run:
```
email:    admin@example.com
password: admin123
```

---

## Docker — self-hosted in one command

```bash
docker compose up -d --build
# open http://localhost:8080
```

The stack exposes the frontend on **port 8080** and the inbound listener on **port 25**. 

### docker-compose env vars
| Var | Default | Purpose |
|-----|---------|---------|
| `MONGO_URL` | `mongodb://mongo:27017` | Database connection |
| `JWT_SECRET` | `change-me…` | Sign JWTs. **CHANGE THIS.** |
| `ADMIN_EMAIL` | `admin@example.com` | Initial admin |
| `ADMIN_PASSWORD` | `admin123` | Initial admin password |
| `FRONTEND_URL` | `http://localhost:8080` | CORS allow-list |

---

## API surface (prefixed with `/api`)

### Auth & Tokens
- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET/POST/DELETE /tokens` — Generate and manage `re_` prefixed API keys for automation.

### Domains
- `GET/POST /domains`, `GET/PATCH/DELETE /domains/{id}`
- `GET /domains/{id}/dns` — generated SPF / DKIM / DMARC / MX records
- `POST /domains/{id}/verify` — live DNS checks + score

### Mailboxes, Aliases & Inbound
- `GET/POST/PATCH/DELETE /mailboxes[/{id}]`
- `GET/POST/PATCH/DELETE /aliases[/{id}]`
- `GET /inbound/messages` — Read received emails
- `GET /inbound/stats` — Inbound metrics

### Relays, Tasks & Logs
- `GET/POST/PATCH/DELETE /relays[/{id}]`
- `GET /relays/tasks` — Background worker queue status
- `POST /send/test` — Push email to background queue
- `GET /logs`, `POST /logs/{id}/retry`, `DELETE /logs/{id}`

### Deliverability & Stats
- `GET /stats` — Dashboard counters + recent logs
- `GET /deliverability` — Live DNS checks over all domains

---

## Product philosophy

Relayd IS: a modern, relay-aware, self-hostable, modular, lightweight,
developer-friendly and privacy-focused email orchestration platform.

Relayd IS NOT: a cPanel clone, a traditional hosting panel, a heavy enterprise
mail suite, or an old-school Postfix UI.

---

## License

MIT — fork it, host it, hack on it.

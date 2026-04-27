# Deployment — Wysraq

> First time deploying anything in my life. Done in a single day.

---

## The Problem

Running the bot on my laptop meant:
- Closing the laptop = bot dies
- Power cut = bot dies  
- Going to university = bot dies

The fix? A server that never sleeps.

---

## Architecture

![Deployment Architecture](https://github.com/user-attachments/assets/d66ac13d-0991-48a9-9468-a7bd9f603a2a)

---

## Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Server | DigitalOcean (Singapore) | Always-on Linux machine |
| Process Manager | PM2 | Keeps FastAPI + Node.js alive 24/7 |
| Reverse Proxy | Nginx | Routes wysraq.me → correct port |
| SSL | Certbot (Let's Encrypt) | Free HTTPS |
| Database | PostgreSQL | Stores users, Q&A, conversations |
| AI | Groq (Llama 3.3 70B) | Intent routing + reply generation |

---

## How Traffic Flows
User visits wysraq.me
↓
Nginx (port 443, HTTPS)
↓
Landing page → served directly by Nginx
Dashboard   → forwarded to Node.js (port 3000)
API calls   → forwarded to FastAPI (port 8000)
↓
FastAPI calls Groq AI
↓
Reply sent back to WhatsApp

---

## PM2 Processes

```bash
pm2 list
# wysraq-api   → uvicorn main:app (FastAPI)
# wysraq-bot   → node index.js (WhatsApp switchboard)
```

---

## Deployment Steps (what I actually did)

1. Created DigitalOcean droplet (Ubuntu 24.04)
2. Installed Python, Node.js, PostgreSQL, Chrome libs
3. Cloned repo via `git clone`
4. Set up `.env` with all secrets
5. Configured Nginx + got SSL via Certbot
6. Started both servers with PM2
7. Set up `git pull` workflow for updates

---

## Update Workflow

```bash
# On laptop
git push

# On server
cd /root/wysraq-whatsapp-ai-agent
git pull
pm2 restart all
```

---

## Live

🌐 [wysraq.me](https://wysraq.me)

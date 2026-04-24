# Wysraq: The Invisible WhatsApp AI 👻

> Tired of AI bots replying to your mom? You're in the right place.

---

## Why Does This Even Exist?

I was in a TCF scholarship group on WhatsApp.  
Our sir used to message almost every week:

> *"Beta please mujhe personal msg karna band kar dein"*  
> *"Guys please! Don't ask the same question again and again personally."*

Every Saturday, same reminder — **don't message on weekends.**

This guy was using WhatsApp for work, but his personal life was being destroyed by it.  
Every AI agent I found either replied to *everything*, or cost money.

So I built something that actually understands the difference. **For free.**

---

## What is Wysraq?

A dual-server app that turns your personal WhatsApp into a **24/7 business agent** — without touching your personal messages.

It runs a hidden browser on your computer, catches incoming messages, and uses AI to reply to customers. Your family? It leaves them alone.

---

## How is it Different?

Most bots are blind — they reply to **everything.**

Wysraq uses **Intent-Based Routing:**

| Message | What Wysraq Does |
|---|---|
| *"What are your business hours?"* | ✅ AI replies instantly |
| *"Dahi le kar aao?"* (your brother) | 👻 Ignored. Left unread. |

---

### 5. Why Wysraq?
I was in a TCF (The Citizens Foundation) scholarship group on WhatsApp. Our sir used to message almost every week — "Beta please mujhe personal msg karna band kar dein" or "Guys please! Don't ask the same question again and again personally." Every Saturday he'd remind us: don't message on weekends.

And I kept thinking — this guy is clearly using WhatsApp for his work group, but his personal life is getting destroyed because of it.

Most AI WhatsApp agents I found either reply to everything or cost money. So I thought, what if I just... build something that actually understands the difference? And make it free. That's Wysraq.

### 6. how does Wysraq work?

```mermaid
graph TD;
    User[Customer/Friend on WhatsApp] -->|Sends Message| Node[Node.js Switchboard]
    Node -->|Forwards text| FastAPI{Python FastAPI Brain}
    FastAPI -->|Check Intent| Groq[Groq Llama-3 API]
    
    Groq -->|Intent: Personal / 'Dahi'| Ignore[Ignore! Do nothing]
    Groq -->|Intent: Business| DB[(PostgreSQL Vault)]
    
    DB -->|Fetch Q&A Data| Groq
    Groq -->|Generate Reply| Node
    Node -->|Send WhatsApp Message| User

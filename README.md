 # Wysraq: The Invisible WhatsApp AI 👻

Hey there! If you are tired of AI bots replying to your mom, you are in the right place. 

### 1. What is Wysraq?
Simply put, Wysraq is a dual-server software that turns your standard personal WhatsApp number into a 24/7 intelligent business agent. It runs a hidden web browser on your computer to catch your messages and uses AI to reply to your customers for you.

### 2. Why is it different from the millions of other bots?
Most WhatsApp bots are blind. If you hook them up to your phone, they reply to *every single message*. 

Wysraq uses **Intent-Based Routing**. 
If a customer messages you: *"What are your business hours?"* → The AI answers instantly.
If your brother messages you: *"Dahi le kar aao?"* (Bring yogurt) → The AI acts like it doesn't exist. It ignores the message, leaves it unread, and doesn't interrupt your personal life. 

### 3. How does it work? (The Architecture)
We split the brain from the body. Node.js handles the WhatsApp connection, and Python handles the AI logic. 

### 4. why Wysraq?
I was in a TCF (The Citizens Foundation) scholarship group on WhatsApp. Our sir used to message almost every week — "Beta please mujhe personal msg karna band kar dein" or "Guys please! Don't ask the same question again and again personally." Every Saturday he'd remind us: don't message on weekends.

And I kept thinking — this guy is clearly using WhatsApp for his work group, but his personal life is getting destroyed because of it.

Most AI WhatsApp agents I found either reply to everything or cost money. So I thought, what if I just... build something that actually understands the difference? And make it free. That's Wysraq.

### 5. how does Wysraq work?

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

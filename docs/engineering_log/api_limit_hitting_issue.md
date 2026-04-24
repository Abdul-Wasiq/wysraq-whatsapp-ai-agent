# 002: Beating Rate Limits with a Circular Queue
**April 2026** · Solved ✅

---

## The Problem, in one line:
> 5 messages arrive at once → Groq free tier panics → AI goes silent 💀

---

## The Fix, in one line:
> 5 free API keys + circular rotation = 5x the capacity, $0 spent

---

## How it works
[KEY_1] → [KEY_2] → [KEY_3] → [KEY_4] → [KEY_5]
↓
loops back to [KEY_1] 

Every new message gets the *next* key in line.  
When it hits the end? Modulo operator sends it back to the start.

```python
current_index = (current_index + 1) % len(api_keys)
```

That one line **is** the circular queue.

---

## Why not just... pay for premium?
This is a free tool. Paying isn't an option.  
Dropping requests isn't either.  
DSA was. 

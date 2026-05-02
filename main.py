from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any

from fastapi import FastAPI
from database import getUser, addUser, configration, getConfig, addQAs, delQA, getUserQA, getConversations, saveConversation    
from fastapi.middleware.cors import CORSMiddleware

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from jose import JWTError, jwt

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")  
ALGORITHM = "HS256"

API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"

BASE_DIR = Path(__file__).resolve().parent

QA_FILE = BASE_DIR / "qa_data.json"
STATS_FILE = BASE_DIR / "stats.json"
LEGACY_FILE = BASE_DIR / "data.json"

storage_lock = threading.Lock()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SetupPayload(BaseModel):
    token: str
    business_description: str = ""
    owner_number: str = ""

class QAItem(BaseModel):
    question: str
    answer: str


class QAPayload(BaseModel):
    qa: list[QAItem] = Field(default_factory=list)


class Message(BaseModel):
    phone: str
    message: str

class AuthPayload(BaseModel):
    username: str = ""
    password: str
    email: str

class ConfigPayload(BaseModel):
    config: str
    phoneNum: str

class QAPayload(BaseModel):
    token: str
    qa: list[QAItem] = Field(default_factory=list)

class Message(BaseModel):
    user_id: int
    phone: str
    message: str
    reply_to_groups: bool = False

class GoogleAuthPayload(BaseModel):
    credential: str
    
# def _read_json(file_path: Path, default: Any) -> Any:
#     if not file_path.exists():
#         return default
#     try:
#         with file_path.open("r", encoding="utf-8") as f:
#             return json.load(f)
#     except Exception:
#         return default


def _write_json(file_path: Path, data: Any) -> None:
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_owner_number(owner_number: str) -> str:
    number = (owner_number or "").strip()
    if not number:
        return ""
    return number if number.endswith("@c.us") else f"{number}@c.us"


# def _ensure_storage() -> None:
#     with storage_lock:
#         qa_data = _read_json(QA_FILE, None)
#         stats = _read_json(STATS_FILE, None)

#         if qa_data is None:
#             legacy = _read_json(LEGACY_FILE, {})
#             qa_data = {"qa": legacy.get("qa", [])}

#         if stats is None:
#             stats = {
#                 "total_messages": 0,
#                 "answered_messages": 0,
#                 "ignored_messages": 0,
#                 "conversations": [],
#             }

#         _write_json(QA_FILE, qa_data)
#         _write_json(STATS_FILE, stats)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_display() -> str:
    return datetime.now().strftime("%I:%M %p")


# def _get_stats() -> dict[str, Any]:
#     return _read_json(
#         STATS_FILE,
#         {
#             "total_messages": 0,
#             "answered_messages": 0,
#             "ignored_messages": 0,
#             "conversations": [],
#         },
#     )


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}

    try:
        return json.loads(raw)
    except Exception:
        pass

    first = raw.find("{")
    last = raw.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return {}

    snippet = raw[first : last + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return {}


def _call_groq(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is missing in .env")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=40)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _build_decision_prompt(config: dict[str, Any], qa_items: list[dict[str, str]]) -> str:
    qa_text_lines: list[str] = []
    for idx, item in enumerate(qa_items):
        qa_text_lines.append(
            f"{idx}. QUESTION: {item.get('question', '')}\n   ANSWER: {item.get('answer', '')}"
        )
    qa_text = "\n".join(qa_text_lines) if qa_text_lines else "No Q&A pairs available."

    return (
        "You are an EXTREMELY strict intent classifier for a WhatsApp business assistant.\n"
        f"Business description: {config.get('business_description', '')}\n\n"
        "Q&A knowledge base:\n"
        f"{qa_text}\n\n"
        "YOUR ONLY JOB: Decide if this message is DIRECTLY asking about this specific business.\n\n"
        "STRICT RULES:\n"
        "1) is_business_query=true ONLY IF the message is CLEARLY and DIRECTLY asking about "
        "this business's services, products, pricing, hours, availability, or process.\n"
        "2) WHEN IN DOUBT → is_business_query=false. A false negative (missing a real query) "
        "is FAR better than a false positive (replying to a wrong message).\n"
        "3) ALWAYS false — no exceptions:\n"
        "   - Greetings with no business question (Hi, Hello, Salam, Assalamualaikum)\n"
        "   - Personal, casual, or emotional messages\n"
        "   - Announcements or statements not directed at the business\n"
        "   - Instructions or commands to the bot itself\n"
        "   - Messages that are complaints, rants, or unrelated opinions\n"
        "   - Any message where you are not 100% sure it is about THIS business\n"
        "4) Language: match by MEANING across Urdu, Roman Urdu, English — not exact words.\n"
        "5) Q&A matching: only match if the core intent is IDENTICAL. "
        "One similar word is NOT enough. If unsure → qa_index=-1.\n"
        "6) If qa_index=-1 but is_business_query=true, the answer will be AI-generated.\n\n"
        "Return STRICT JSON only, no explanation, no markdown:\n"
        '{"is_business_query": true/false, "qa_index": number, "reason": "short reason"}'
    )

def _build_judge_prompt(config: dict[str, Any], qa_items: list[dict[str, str]], original_message: str, gate1_reason: str) -> str:
    qa_text_lines: list[str] = []
    for idx, item in enumerate(qa_items):
        qa_text_lines.append(
            f"{idx}. QUESTION: {item.get('question', '')}\n   ANSWER: {item.get('answer', '')}"
        )
    qa_text = "\n".join(qa_text_lines) if qa_text_lines else "No Q&A pairs available."
 
    return (
        "You are a JUDGE reviewing a decision made by another AI.\n"
        f"Business description: {config.get('business_description', '')}\n\n"
        "Q&A knowledge base:\n"
        f"{qa_text}\n\n"
        f"The message received was: \"{original_message}\"\n"
        f"The first AI said this IS a business query. Its reason: \"{gate1_reason}\"\n\n"
        "YOUR JOB: Verify this decision. Be a skeptic. Ask yourself:\n"
        "- Is this message GENUINELY asking about this specific business?\n"
        "- Could this message be personal, casual, or unrelated?\n"
        "- Would a reasonable human business owner want to reply to this?\n"
        "- Is the first AI's reason convincing and logical?\n\n"
        "STRICT RULE: If you have ANY doubt → approve=false.\n"
        "It is better to miss a customer than to embarrass the business owner.\n\n"
        "Return STRICT JSON only, no explanation, no markdown:\n"
        '{"approve": true/false, "reason": "short reason"}'
    )
 
def _build_answer_prompt(config: dict[str, Any], user_message: str) -> str:
    return (
        "You are a WhatsApp business assistant.\n"
        f"Business description: {config.get('business_description', '')}\n\n"
        "Rules:\n"
        "1) Give a concise, helpful response based on business context.\n"
        "2) Match user's language style (Roman Urdu/Urdu-English/English).\n"
        "3) Do not invent policies beyond given context.\n"
        "4) Keep response short and WhatsApp-friendly.\n"
        f"\nUser message: {user_message}"
    )


@app.get("/setup")
def get_setup(token: str = "") -> dict[str, Any]:
    try:
        user_id = verifyToken(token)
        config = getConfig(user_id)
        if config:
            return {
                "business_description": config["business_description"],
                "owner_number": config["phone_num"]
            }
    except:
        pass
    return {"business_description": "", "owner_number": ""}

@app.post("/setup")
def save_setup(payload: SetupPayload) -> dict[str, Any]:
    try:
        user_id = verifyToken(payload.token)
        print(f">>> TOKEN VERIFIED: user_id = {user_id}")
    except JWTError as e:
        print(f">>> JWT ERROR: {e}")
        return {"success": False, "message": "Invalid token! Who are you? 🤨"}
    except Exception as e:
        print(f">>> OTHER ERROR: {e}")
        return {"success": False, "message": "Invalid token! Who are you? 🤨"}
    
    success = configration(user_id, payload.business_description, payload.owner_number)
    if success:
        return {"success": True}
    else:
        return {"success": False, "message": "Setup failed. Check Python terminal!"}
    
   

# @app.get("/stats")
# def get_stats() -> dict[str, Any]:
#     stats = _get_stats()
#     return {
#         "total_messages": int(stats.get("total_messages", 0)),
#         "answered_messages": int(stats.get("answered_messages", 0)),
#         "ignored_messages": int(stats.get("ignored_messages", 0)),
#     }


@app.get("/conversations")
def get_conversations(token: str = "") -> list[dict[str, Any]]:
    try:
        # 1. The Security Checkpoint: Extract the REAL ID from the unhackable token
        user_id = verifyToken(token)
        
        # 2. Fetch only that user's data
        convos = getConversations(user_id)
        
        # 3. Format the data slightly so your HTML can read it perfectly
        formatted_convos = []
        for c in convos:
            formatted_convos.append({
                "phone": c["custphon"],
                "message": c["message"],
                "reply": c["reply"],
                "status": c["status"],
                # Convert the PostgreSQL timestamp to a readable string like "2:32 PM"
                "time": c["created_at"].strftime("%I:%M %p") if c["created_at"] else ""
            })
            
        return formatted_convos
        
    except Exception as e:
        print(f"Auth or DB error: {e}")
        # If the hacker provides a bad token, send them an empty list!
        return []

def createToken(user_id: int) -> str:
    return jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm=ALGORITHM)

def verifyToken(token: str) -> int:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload.get("user_id")

@app.get("/qa")
def get_qa(token: str = "") -> dict[str, Any]:
    try:
        # 1. Who is asking?
        user_id = verifyToken(token)
        
        # 2. Get their specific questions from the database
        qa_list = getUserQA(user_id)
        
        # 3. Send it to the frontend
        return {"qa": qa_list}
    except Exception as e:
        print(f"Error loading QA: {e}")
        # If token fails or no data, send an empty list
        return {"qa": []}

@app.post("/chat")
def chat(msg: Message) -> dict[str, Any]:
    config = getConfig(msg.user_id) 
    qa_items = getUserQA(msg.user_id) 
    
    if not config:
        config = {"business_description": "No description provided", "owner_number": ""}

    print(f"Phone: {msg.phone}")
    print(f"Message: {msg.message}")
    print(f"Reply to groups: {msg.reply_to_groups}")

    # ── GROUP FILTER ──────────────────────────────
    is_group = msg.phone.endswith("@g.us")
    if is_group and not msg.reply_to_groups:
        print(f"🚫 Group message ignored (reply_to_groups=False)")
        return {"status": "ignored", "reply": None, "owner": config.get("owner_number", "")}

    # ── GATE 1: Intent Classifier ─────────────────
    decision_prompt = _build_decision_prompt(config, qa_items)
    decision_raw = _call_groq(decision_prompt, msg.message, temperature=0.0)
    decision = _extract_json_object(decision_raw)

    is_business_query = bool(decision.get("is_business_query", False))
    qa_index = int(decision.get("qa_index", -1)) if str(decision.get("qa_index", "-1")).lstrip("-").isdigit() else -1
    gate1_reason = decision.get("reason", "")

    print(f"Gate 1 → is_business_query={is_business_query}, reason={gate1_reason}")

    # ── REPLY ─────────────────────────────────────
    if not is_business_query:
        status = "ignored"
        reply = None
    else:
        status = "answered"
        if 0 <= qa_index < len(qa_items):
            reply = qa_items[qa_index]["answer"]
        else:
            answer_prompt = _build_answer_prompt(config, msg.message)
            reply = _call_groq(answer_prompt, msg.message, temperature=0.3)

    save_success = saveConversation(msg.user_id, msg.phone, msg.message, reply, status)
    
    if save_success:
        print(f"✅ Saved conversation for {msg.phone} to database.")
    else:
        print("❌ Failed to save conversation to database.")

    return {
        "status": status,
        "reply": reply,
        "owner": config.get("owner_number", ""),
    }

# HANDLING DATABASE

@app.post("/login")
def loginUser(payload: AuthPayload):
    user = getUser(payload.email, payload.password)
    
    if user:
        token = createToken(user["id"])
        return {"success": True, "token": token, "user_id": user["id"]}
    else:
        return {"success": False, "message": "Invalid username or password"}
    
@app.post("/signup")
def signupUser(payload: AuthPayload):
    success = addUser(payload.username, payload.password, payload.email)

    if success == True:
        user = getUser(payload.email, payload.password)
        token = createToken(user["id"])
        return {"success": True, "token": token, "user_id": user["id"]}
    elif success == "duplicate":
        return {"success": False, "message": "bacha ziada smart na ban, double subscription nhi milne wali, (You already exist)"}
    else:
        return {"success": False, "message": "Database insertion failed. Check your Python terminal for the real error!"}
    

@app.post("/setup")
def save_setup(payload: SetupPayload) -> dict[str, Any]:
    success = configration(payload.user_id, payload.business_description, payload.owner_number)
    if success:
        return {"success": True}
    else:
        return {"success": False, "message": "Setup failed. Check Python terminal!"}
    

@app.post("/qa")
def save_qa(payload: QAPayload):
    try:
        user_id = verifyToken(payload.token)
        
        # DELETE ONCE BEFORE THE LOOP
        delQA(user_id) 
        
        # NOW LOOP AND INSERT
        for item in payload.qa:
            addQAs(user_id, item.question, item.answer)
            print(f"Saved: {item.question}")

        return {"success": True, "message": "Q&A updated in database"}
    except Exception as e:
        return {"success": False, "message": str(e)} 

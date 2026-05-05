from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from database import getUser, addUser, configration, getConfig, addQAs, delQA, getUserQA, getConversations, saveConversation, getUserPlan, getQACount, setPremium, getAllUsers
from fastapi.middleware.cors import CORSMiddleware

import requests
from dotenv import load_dotenv
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

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

FREE_QA_LIMIT = 3
PREMIUM_QA_LIMIT = 15 

BASE_DIR = Path(__file__).resolve().parent
storage_lock = threading.Lock()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TokenOnlyPayload(BaseModel):
    token: str

class SetupPayload(BaseModel):
    token: str
    business_description: str = ""
    owner_number: str = ""

class QAItem(BaseModel):
    question: str
    answer: str

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

class AuthPayload(BaseModel):
    username: str = ""
    password: str
    email: str

class AdminLoginPayload(BaseModel):
    password: str

class PremiumPayload(BaseModel):
    admin_password: str
    user_id: int
    is_premium: bool


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
    snippet = raw[first: last + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return {}

def _call_groq(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is missing in .env")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
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
    return response.json()["choices"][0]["message"]["content"].strip()

def _build_decision_prompt(config: dict[str, Any], qa_items: list[dict[str, str]]) -> str:
    qa_text_lines: list[str] = []
    for idx, item in enumerate(qa_items):
        qa_text_lines.append(f"{idx}. QUESTION: {item.get('question', '')}\n   ANSWER: {item.get('answer', '')}")
    qa_text = "\n".join(qa_text_lines) if qa_text_lines else "No Q&A pairs available."
    return (
        "You are an EXTREMELY strict intent classifier for a WhatsApp business assistant.\n"
        f"Business description: {config.get('business_description', '')}\n\n"
        "Q&A knowledge base:\n"
        f"{qa_text}\n\n"
        "YOUR ONLY JOB: Decide if this message is DIRECTLY asking about this specific business.\n\n"
        "STRICT RULES:\n"
        "1) is_business_query=true ONLY IF the message is CLEARLY and DIRECTLY asking about this business.\n"
        "2) WHEN IN DOUBT → is_business_query=false.\n"
        "3) ALWAYS false: greetings only, personal/casual messages, announcements, bot commands, rants.\n"
        "4) Language: match by MEANING across Urdu, Roman Urdu, English.\n"
        "5) Q&A matching: only match if core intent is IDENTICAL. If unsure → qa_index=-1.\n\n"
        "Return STRICT JSON only:\n"
        '{"is_business_query": true/false, "qa_index": number, "reason": "short reason"}'
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

def createToken(user_id: int) -> str:
    return jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm=ALGORITHM)

def verifyToken(token: str) -> int:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload.get("user_id")


# ── AUTH ──────────────────────────────────────────────────

@app.post("/login")
def loginUser(payload: AuthPayload):
    user = getUser(payload.email, payload.password)
    if user:
        token = createToken(user["id"])
        return {"success": True, "token": token, "user_id": user["id"]}
    return {"success": False, "message": "Invalid username or password"}

@app.post("/signup")
def signupUser(payload: AuthPayload):
    success = addUser(payload.username, payload.password, payload.email)
    if success == True:
        user = getUser(payload.email, payload.password)
        token = createToken(user["id"])
        return {"success": True, "token": token, "user_id": user["id"]}
    elif success == "duplicate":
        return {"success": False, "message": "You already have an account! Please sign in."}
    return {"success": False, "message": "Signup failed. Please try again."}

@app.post("/auth/google")
def googleAuth(payload: GoogleAuthPayload):
    try:
        GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
        idinfo = id_token.verify_oauth2_token(payload.credential, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = idinfo.get("email")
        name = idinfo.get("name", email.split("@")[0])
        if not email:
            return {"success": False, "message": "Could not get email from Google"}
        conn = None
        try:
            from database import dbConn
            from psycopg2.extras import RealDictCursor
            conn = dbConn()
            curs = conn.cursor(cursor_factory=RealDictCursor)
            curs.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = curs.fetchone()
            if not user:
                curs.execute("INSERT INTO users(name, email, password) VALUES(%s, %s, %s) RETURNING *", (name, email, "GOOGLE_AUTH"))
                conn.commit()
                curs.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = curs.fetchone()
            token = createToken(user["id"])
            return {"success": True, "token": token, "user_id": user["id"]}
        finally:
            if conn:
                curs.close()
                conn.close()
    except Exception as e:
        print(f"Google auth error: {e}")
        return {"success": False, "message": "Google authentication failed"}


# ── SETUP ─────────────────────────────────────────────────

@app.get("/setup")
def get_setup(token: str = "") -> dict[str, Any]:
    try:
        user_id = verifyToken(token)
        config = getConfig(user_id)
        if config:
            return {"business_description": config["business_description"], "owner_number": config["phone_num"]}
    except:
        pass
    return {"business_description": "", "owner_number": ""}

@app.post("/setup")
def save_setup(payload: SetupPayload) -> dict[str, Any]:
    try:
        user_id = verifyToken(payload.token)
    except Exception:
        return {"success": False, "message": "Invalid token!"}
    success = configration(user_id, payload.business_description, payload.owner_number)
    return {"success": True} if success else {"success": False, "message": "Setup failed."}


# ── Q&A ───────────────────────────────────────────────────

@app.get("/qa")
def get_qa(token: str = "") -> dict[str, Any]:
    try:
        user_id = verifyToken(token)
        qa_list = getUserQA(user_id)
        is_premium = getUserPlan(user_id)
        qa_limit = PREMIUM_QA_LIMIT if is_premium else FREE_QA_LIMIT
        return {"qa": qa_list, "is_premium": is_premium, "qa_limit": qa_limit, "qa_count": len(qa_list)}
    except Exception as e:
        print(f"Error loading QA: {e}")
        return {"qa": [], "is_premium": False, "qa_limit": FREE_QA_LIMIT, "qa_count": 0}

@app.post("/qa")
def save_qa(payload: QAPayload):
    try:
        user_id = verifyToken(payload.token)
        is_premium = getUserPlan(user_id)
        qa_limit = PREMIUM_QA_LIMIT if is_premium else FREE_QA_LIMIT

        if len(payload.qa) > qa_limit:
            return {
                "success": False,
                "limit_exceeded": True,
                "message": f"You can only save {qa_limit} Q&A pairs on your current plan.",
                "qa_limit": qa_limit,
                "is_premium": is_premium
            }

        delQA(user_id)
        for item in payload.qa:
            addQAs(user_id, item.question, item.answer)
            print(f"Saved: {item.question}")
        return {"success": True, "message": "Q&A updated"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── PLAN ──────────────────────────────────────────────────

@app.get("/plan")
def get_plan(token: str = "") -> dict[str, Any]:
    try:
        user_id = verifyToken(token)
        is_premium = getUserPlan(user_id)
        qa_count = getQACount(user_id)
        qa_limit = PREMIUM_QA_LIMIT if is_premium else FREE_QA_LIMIT
        return {"is_premium": is_premium, "qa_count": qa_count, "qa_limit": qa_limit, "plan": "Premium" if is_premium else "Free"}
    except Exception as e:
        return {"is_premium": False, "qa_count": 0, "qa_limit": FREE_QA_LIMIT, "plan": "Free"}


# ── CONVERSATIONS ─────────────────────────────────────────

@app.get("/conversations")
def get_conversations(token: str = "") -> list[dict[str, Any]]:
    try:
        user_id = verifyToken(token)
        convos = getConversations(user_id)
        return [{
            "phone": c["custphon"],
            "message": c["message"],
            "reply": c["reply"],
            "status": c["status"],
            "time": c["created_at"].strftime("%I:%M %p") if c["created_at"] else ""
        } for c in convos]
    except Exception as e:
        print(f"Auth or DB error: {e}")
        return []


# ── CHAT ──────────────────────────────────────────────────

@app.post("/chat")
def chat(msg: Message) -> dict[str, Any]:
    config = getConfig(msg.user_id)
    qa_items = getUserQA(msg.user_id)
    if not config:
        config = {"business_description": "No description provided", "owner_number": ""}

    print(f"Phone: {msg.phone} | Message: {msg.message} | Groups: {msg.reply_to_groups}")

    is_group = msg.phone.endswith("@g.us")
    if is_group and not msg.reply_to_groups:
        print(f"🚫 Group message ignored")
        return {"status": "ignored", "reply": None, "owner": config.get("owner_number", "")}

    decision_prompt = _build_decision_prompt(config, qa_items)
    decision_raw = _call_groq(decision_prompt, msg.message, temperature=0.0)
    decision = _extract_json_object(decision_raw)

    is_business_query = bool(decision.get("is_business_query", False))
    qa_index = int(decision.get("qa_index", -1)) if str(decision.get("qa_index", "-1")).lstrip("-").isdigit() else -1
    print(f"Gate 1 → is_business_query={is_business_query}, reason={decision.get('reason', '')}")

    if not is_business_query:
        status = "ignored"
        reply = None
    else:
        status = "answered"
        if 0 <= qa_index < len(qa_items):
            reply = qa_items[qa_index]["answer"]
        else:
            reply = _call_groq(_build_answer_prompt(config, msg.message), msg.message, temperature=0.3)

    saveConversation(msg.user_id, msg.phone, msg.message, reply, status)
    return {"status": status, "reply": reply, "owner": config.get("owner_number", "")}


# ── ADMIN ─────────────────────────────────────────────────

@app.post("/admin/login")
def adminLogin(payload: AdminLoginPayload):
    if payload.password == ADMIN_PASSWORD:
        return {"success": True}
    return {"success": False, "message": "Wrong password!"}

@app.get("/admin/users")
def adminGetUsers(password: str = ""):
    if password != ADMIN_PASSWORD:
        return {"success": False, "message": "Unauthorized"}
    users = getAllUsers()
    return {"success": True, "users": [{
        "id": u["id"],
        "name": u["name"] or "",
        "email": u["email"],
        "is_premium": bool(u["is_premium"]),
        "plan": "Premium ⭐" if u["is_premium"] else "Free",
        "qa_count": u["qa_count"],
        "total_messages": u["total_messages"],
        "joined": ""
    } for u in users]}

@app.post("/admin/set-premium")
def adminSetPremium(payload: PremiumPayload):
    if payload.admin_password != ADMIN_PASSWORD:
        return {"success": False, "message": "Unauthorized"}
    success = setPremium(payload.user_id, payload.is_premium)
    if success:
        return {"success": True, "message": f"User updated to {'Premium ⭐' if payload.is_premium else 'Free'}"}
    return {"success": False, "message": "Database error"}

@app.get("/admin/stats")
def adminGetStats(password: str = ""):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Forbidden")
    users = getAllUsers()
    total_users = len(users)
    premium_users = sum(1 for u in users if u["is_premium"])
    total_messages = sum(u["total_messages"] or 0 for u in users)
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "total_messages": total_messages
    }

import hashlib
import hmac
from datetime import datetime

JAZZCASH_MERCHANT_ID = os.getenv("JAZZCASH_MERCHANT_ID", "")
JAZZCASH_PASSWORD = os.getenv("JAZZCASH_PASSWORD", "")
JAZZCASH_INTEGRITY_SALT = os.getenv("JAZZCASH_INTEGRITY_SALT", "")
JAZZCASH_RETURN_URL = os.getenv("JAZZCASH_RETURN_URL", "https://wysraq.me/payment-success")
JAZZCASH_ENV = os.getenv("JAZZCASH_ENV", "sandbox")

@app.post("/jazzcash/initiate")
def jazzcashInitiate(payload: TokenOnlyPayload):
    user_id = verifyToken(payload.token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    txn_ref = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}{user_id}"
    txn_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
    txn_expiry = datetime.now().replace(hour=23, minute=59, second=59).strftime("%Y%m%d%H%M%S")
    amount = "88200"  
    
    data_to_hash = "&".join([
    JAZZCASH_INTEGRITY_SALT, JAZZCASH_MERCHANT_ID, JAZZCASH_PASSWORD,
    amount, "", "", txn_datetime, txn_expiry, "PKR", txn_ref
])
    secure_hash = hmac.new(JAZZCASH_INTEGRITY_SALT.encode(), data_to_hash.encode(), hashlib.sha256).hexdigest().upper()
    
    base_url = "https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform" if JAZZCASH_ENV == "sandbox" else "https://payments.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform"
    
    params = {
        "pp_Version": "1.1",
        "pp_TxnType": "MWALLET",
        "pp_Language": "EN",
        "pp_MerchantID": JAZZCASH_MERCHANT_ID,
        "pp_Password": JAZZCASH_PASSWORD,
        "pp_TxnRefNo": txn_ref,
        "pp_Amount": amount,
        "pp_TxnCurrency": "PKR",
        "pp_TxnDateTime": txn_datetime,
        "pp_BillReference": "",
        "pp_Description": "Wysraq Premium",
        "pp_TxnExpiryDateTime": txn_expiry,
        "pp_ReturnURL": JAZZCASH_RETURN_URL,
        "pp_SecureHash": secure_hash,
        "ppmpf_1": str(user_id)
    }
    
    from urllib.parse import urlencode
    redirect_url = f"{base_url}?{urlencode(params)}"
    return {"redirect_url": redirect_url}

@app.post("/jazzcash/webhook")
async def jazzcashWebhook(request: Request):
    form = await request.form()
    data = dict(form)
    response_code = data.get("pp_ResponseCode", "")
    user_id = data.get("ppmpf_1", "")
    if response_code == "000" and user_id:
        setPremium(int(user_id), True)
    return {"status": "ok"}

@app.get("/payment-success")
def paymentSuccess():
    return FileResponse("payment-success.html")
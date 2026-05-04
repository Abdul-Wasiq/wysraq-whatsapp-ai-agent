import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

def dbConn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dbname=os.getenv("DB_NAME"),
        port=os.getenv("DB_PORT")
    )

def getUser(email, password):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM users WHERE email = %s AND password = %s"
        curs.execute(query, (email, password))
        userData = curs.fetchone()
        return userData
    except Exception as e:
        print(f"Database Error(database.py) {e}")
        return False
    finally:
        if (conn):
            curs.close()
            conn.close()


def addUser(name, password, email):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor()
        query = "INSERT INTO users(name, password, email) VALUES(%s, %s,%s)"
        curs.execute(query, (name, password, email))
        conn.commit()
        return True
    except Exception as e:
        print(f"Sign up error from database.py {e}")
        if "users_email_unique" in str(e):
            return "duplicate"
        return False
    finally:
        if (conn):
            curs.close()
            conn.close()


def configration(user_id, desc, phoneNum):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor()
        query = """
            INSERT INTO config(user_id, business_description, phone_num) 
            VALUES(%s, %s, %s) 
            ON CONFLICT(user_id) 
            DO UPDATE SET business_description = %s, phone_num = %s
        """
        print(f">>> EXECUTING QUERY with: {user_id}, {desc}, {phoneNum}")
        curs.execute(query, (user_id, desc, phoneNum, desc, phoneNum))
        print(f">>> ROWS AFFECTED: {curs.rowcount}")
        conn.commit()
        print(f">>> COMMITTED!")
        return True
    except Exception as e:
        print(f"Configuration Error from database.py {e}")
        return False
    finally:
        if conn:
            curs.close()
            conn.close()

def getConfig(user_id):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM config WHERE user_id = %s"
        curs.execute(query, (user_id,))
        return curs.fetchone()
    except Exception as e:
        print(f"getConfig error: {e}")
        return None
    finally:
        if conn:
            curs.close()
            conn.close()

def delQA(user_id):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor()
        query = "DELETE FROM qa WHERE user_id = %s"
        curs.execute(query, (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error on delQA function: {e}")
        return False
    finally:
        if (conn):
            curs.close()
            conn.close()

def addQAs(user_id, question, answer):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor()
        query = "INSERT INTO qa(user_id, question, answer) VALUES (%s, %s, %s)"
        curs.execute(query, (user_id, question, answer))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in addQAs from database.py: {e}")
        return False
    finally:
        if (conn):
            curs.close()
            conn.close()

def getUserQA(user_id):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT question, answer FROM qa WHERE user_id = %s"
        curs.execute(query, (user_id,))
        return curs.fetchall()
    except Exception as e:
        print(f"Error in getUserQA: {e}")
        return []
    finally:
        if conn:
            curs.close()
            conn.close()

def saveConversation(user_id, phone, message, reply, status):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor()
        query = """INSERT INTO conversations (user_id, custphon, message, reply, status) 
                   VALUES (%s, %s, %s, %s, %s)"""
        curs.execute(query, (user_id, phone, message, reply, status))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving conversation: {e}")
        return False
    finally:
        if conn:
            curs.close()
            conn.close()

def getConversations(user_id):
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM conversations WHERE user_id = %s ORDER BY created_at DESC"
        curs.execute(query, (user_id,))
        return curs.fetchall()
    except Exception as e:
        print(f"Error fetching conversations: {e}")
        return []
    finally:
        if conn:
            curs.close()
            conn.close()

# ── PREMIUM / ADMIN FUNCTIONS ─────────────────────────────

def getUserPlan(user_id):
    """Returns True if user is premium, False if free"""
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor(cursor_factory=RealDictCursor)
        curs.execute("SELECT is_premium FROM users WHERE id = %s", (user_id,))
        row = curs.fetchone()
        return bool(row["is_premium"]) if row else False
    except Exception as e:
        print(f"Error in getUserPlan: {e}")
        return False
    finally:
        if conn:
            curs.close()
            conn.close()

def getQACount(user_id):
    """Returns how many Q&A pairs user currently has"""
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor()
        curs.execute("SELECT COUNT(*) FROM qa WHERE user_id = %s", (user_id,))
        return curs.fetchone()[0]
    except Exception as e:
        print(f"Error in getQACount: {e}")
        return 0
    finally:
        if conn:
            curs.close()
            conn.close()

def setPremium(user_id, is_premium: bool):
    """Admin function to upgrade or downgrade a user"""
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor()
        curs.execute("UPDATE users SET is_premium = %s WHERE id = %s", (is_premium, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error in setPremium: {e}")
        return False
    finally:
        if conn:
            curs.close()
            conn.close()

def getAllUsers():
    """Admin function to get all users with their stats"""
    conn = None
    try:
        conn = dbConn()
        curs = conn.cursor(cursor_factory=RealDictCursor)
        curs.execute("""
            SELECT
                u.id,
                u.name,
                u.email,
                u.is_premium,
                COUNT(DISTINCT q.id) as qa_count,
                COUNT(DISTINCT c.id) as total_messages
            FROM users u
            LEFT JOIN qa q ON q.user_id = u.id
            LEFT JOIN conversations c ON c.user_id = u.id
            GROUP BY u.id, u.name, u.email, u.is_premium
            ORDER BY u.id DESC
        """)
        return curs.fetchall()
    except Exception as e:
        print(f"Error in getAllUsers: {e}")
        return []
    finally:
        if conn:
            curs.close()
            conn.close()
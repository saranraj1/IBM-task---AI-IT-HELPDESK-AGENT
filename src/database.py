import os
import json
import sqlite3
import datetime
from pathlib import Path
from contextlib import contextmanager
from src.config import DATABASE_PATH

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(DATABASE_PATH)
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH
DATA_DIR = DB_PATH.parent

_db_initialized = False

def get_connection():
    """Returns a SQLite connection to helpdesk.db with WAL mode enabled."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    # Concurrency and integrity pragmas
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

@contextmanager
def db_session():
    """Context manager for SQLite connections with auto-commit and rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """Initializes the database schema if tables do not exist."""
    global _db_initialized
    if _db_initialized and DB_PATH.exists():
        return
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            
            # Tickets Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT UNIQUE NOT NULL,
                    user_name TEXT NOT NULL,
                    issue TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    created_at TEXT NOT NULL
                )
            """)
            
            # User Memory Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, memory_key) ON CONFLICT REPLACE
                )
            """)

            # Chat Sessions Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Chat Messages Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ticket_card_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                )
            """)
        _db_initialized = True
    except Exception as e:
        print(f"[DB Error] Database initialization failed: {e}")

# ------------------------------------------------------------------------------
# Support Ticket Operations
# ------------------------------------------------------------------------------
def insert_ticket(user_name: str, issue: str, priority: str, ticket_id: str = None) -> dict:
    """Inserts a new ticket record into SQLite."""
    init_db()
    if not ticket_id:
        import random
        num = random.randint(10000, 99999)
        ticket_id = f"TKT-2026-{num}"
        
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tickets (ticket_id, user_name, issue, priority, status, created_at)
                VALUES (?, ?, ?, ?, 'OPEN', ?)
            """, (ticket_id, user_name, issue, priority.upper(), created_at))
            return {
                "ticket_id": ticket_id,
                "user_name": user_name,
                "issue": issue,
                "priority": priority.upper(),
                "status": "OPEN",
                "created_at": created_at
            }
    except Exception as e:
        print(f"[DB Error] Failed to insert ticket: {e}")
        return {"error": str(e)}

def get_ticket(ticket_id: str) -> dict:
    """Retrieves a ticket by ticket_id."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB Error] Failed to get ticket: {e}")
        return None

def get_all_tickets(status: str = None) -> list:
    """Retrieves all tickets, optionally filtered by status ('OPEN' or 'CLOSED')."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM tickets WHERE status = ? ORDER BY id DESC", (status.upper(),))
            else:
                cursor.execute("SELECT * FROM tickets ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB Error] Failed to get tickets: {e}")
        return []

def close_ticket(ticket_id: str) -> bool:
    """Updates status of a ticket to CLOSED."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tickets SET status = 'CLOSED' WHERE ticket_id = ?", (ticket_id.strip().upper(),))
            return cursor.rowcount > 0
    except Exception as e:
        print(f"[DB Error] Failed to close ticket: {e}")
        return False

def get_ticket_stats() -> dict:
    """Returns total open and closed ticket counts."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) as count FROM tickets GROUP BY status")
            rows = cursor.fetchall()
            
            stats = {"OPEN": 0, "CLOSED": 0, "TOTAL": 0}
            for row in rows:
                st = row["status"].upper()
                stats[st] = row["count"]
                stats["TOTAL"] += row["count"]
            return stats
    except Exception as e:
        print(f"[DB Error] Failed to get ticket stats: {e}")
        return {"OPEN": 0, "CLOSED": 0, "TOTAL": 0}

# ------------------------------------------------------------------------------
# Long-Term User Memory Operations
# ------------------------------------------------------------------------------
def save_user_memory(user_id: str, memory_key: str, memory_value: str) -> bool:
    """Saves or updates a fact key-value pair for a user in long-term memory."""
    init_db()
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_memory (user_id, memory_key, memory_value, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, memory_key.lower(), memory_value, created_at))
            return True
    except Exception as e:
        print(f"[DB Error] Failed to save memory: {e}")
        return False

def get_user_memory(user_id: str, memory_key: str = None) -> list:
    """Retrieves long-term memory facts for a user."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            if memory_key:
                cursor.execute("SELECT * FROM user_memory WHERE user_id = ? AND memory_key = ?", (user_id, memory_key.lower()))
            else:
                cursor.execute("SELECT * FROM user_memory WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB Error] Failed to get memory: {e}")
        return []

# ------------------------------------------------------------------------------
# Persistent Chat Session Operations
# ------------------------------------------------------------------------------
def get_or_create_chat_session(session_id: str, title: str = "Support Chat") -> dict:
    """Gets an existing chat session or creates a new one."""
    init_db()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            cursor.execute("""
                INSERT INTO chat_sessions (session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (session_id, title, now, now))
            return {"session_id": session_id, "title": title, "created_at": now, "updated_at": now}
    except Exception as e:
        print(f"[DB Error] Failed to get/create chat session: {e}")
        return {"session_id": session_id, "title": title, "created_at": now, "updated_at": now}

def save_chat_message(session_id: str, role: str, content: str, ticket_card: dict = None) -> bool:
    """Appends a message to persistent chat history."""
    init_db()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticket_json = json.dumps(ticket_card) if ticket_card else None
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            # Ensure session exists
            cursor.execute("SELECT session_id FROM chat_sessions WHERE session_id = ?", (session_id,))
            if not cursor.fetchone():
                # Generate dynamic title from initial user message
                title = content[:30] + ("..." if len(content) > 30 else "") if role == "user" else "Support Chat"
                cursor.execute("""
                    INSERT INTO chat_sessions (session_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (session_id, title, now, now))
            else:
                cursor.execute("UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))

            cursor.execute("""
                INSERT INTO chat_messages (session_id, role, content, ticket_card_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, role, content, ticket_json, now))
            return True
    except Exception as e:
        print(f"[DB Error] Failed to save chat message: {e}")
        return False

def get_chat_history(session_id: str) -> list:
    """Retrieves all chat messages for a given session."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, ticket_card_json, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))
            rows = cursor.fetchall()
            messages = []
            for r in rows:
                msg = {
                    "role": r["role"],
                    "content": r["content"],
                    "created_at": r["created_at"]
                }
                if r["ticket_card_json"]:
                    try:
                        msg["ticket_card"] = json.loads(r["ticket_card_json"])
                    except Exception:
                        pass
                messages.append(msg)
            return messages
    except Exception as e:
        print(f"[DB Error] Failed to get chat history: {e}")
        return []

def list_chat_sessions(limit: int = 15) -> list:
    """Returns recent chat sessions."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, title, created_at, updated_at
                FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"[DB Error] Failed to list chat sessions: {e}")
        return []

def delete_chat_session(session_id: str) -> bool:
    """Deletes a chat session and all its messages."""
    init_db()
    try:
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
            return True
    except Exception as e:
        print(f"[DB Error] Failed to delete chat session: {e}")
        return False

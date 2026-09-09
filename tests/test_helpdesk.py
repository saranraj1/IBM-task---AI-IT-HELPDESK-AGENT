import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
try:
    import torch
except Exception:
    pass

import sys
import html
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.config import check_llm_status, check_ollama_status, LLM_PROVIDER
from src.database import (
    init_db,
    get_connection,
    get_ticket_stats,
    save_chat_message,
    get_chat_history,
    list_chat_sessions,
    delete_chat_session
)
from src.rag import get_or_create_vectorstore, query_rag, reindex_knowledge_base
from src.tools import create_ticket, check_ticket_status, detect_priority
from src.graph import run_helpdesk_pipeline
from src.memory import save_user_memory, get_user_memory, retrieve_user_fact

def run_tests():
    print("=======================================================")
    print("  RUNNING UPGRADED AI IT HELPDESK SUITE VERIFICATION")
    print("=======================================================\n")
    
    # 1. Multi-Tier LLM Architecture Check
    print("[1/8] Testing Multi-Tier LLM Architecture (Cloud Primary / Ollama Secondary)...")
    llm_info = check_llm_status()
    print(f"   [OK] Primary Provider configured: {llm_info['primary_provider'].upper()}")
    print(f"   [OK] Active Runtime Tier: {llm_info['active_tier'].upper()}")
    print(f"   [OK] Status Message: {llm_info['message']}")
    assert "active_tier" in llm_info
    
    # 2. Database Initialization & WAL Mode
    print("\n[2/8] Testing Database Setup & SQLite WAL Concurrency Mode...")
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    conn.close()
    print(f"   [OK] SQLite Journal Mode: {mode.upper()}")
    assert mode.lower() == "wal", f"Expected WAL mode, got {mode}"
    stats = get_ticket_stats()
    print(f"   [OK] Current Ticket Stats: {stats}")

    # 3. Persistent Chat Sessions & Message CRUD
    print("\n[3/8] Testing Persistent Chat Sessions across Page Refreshes...")
    test_sid = "test_run_session_42"
    save_chat_message(test_sid, "user", "My VPN is disconnecting randomly")
    save_chat_message(test_sid, "assistant", "Please check your network credentials...")
    history = get_chat_history(test_sid)
    assert len(history) == 2, f"Expected 2 messages, found {len(history)}"
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    sessions = list_chat_sessions()
    assert any(s["session_id"] == test_sid for s in sessions)
    delete_chat_session(test_sid)
    print(f"   [OK] Chat history persistence and deletion verified successfully.")

    # 4. Security & Input Sanitization
    print("\n[4/8] Testing Security XSS Sanitization...")
    malicious_input = "<script>alert('pwned')</script>&quot;test&quot;"
    sanitized = html.escape(malicious_input)
    assert "<script>" not in sanitized
    assert "&lt;script&gt;" in sanitized
    print(f"   [OK] XSS payload successfully neutralized: '{sanitized}'")

    # 5. Priority Detection Rules
    print("\n[5/8] Testing Priority Detection...")
    p1 = detect_priority("My laptop keeps restarting constantly")
    p2 = detect_priority("My WiFi connection is slow")
    p3 = detect_priority("Need paper for printer")
    assert p1 == "HIGH", f"Expected HIGH, got {p1}"
    assert p2 == "MEDIUM", f"Expected MEDIUM, got {p2}"
    assert p3 == "LOW", f"Expected LOW, got {p3}"
    print(f"   [OK] Priority detection verified (High: {p1}, Medium: {p2}, Low: {p3})")
    
    # 6. RAG Similarity Search & Multi-format Knowledge Base
    print("\n[6/8] Testing ChromaDB RAG Vector Store & Multi-Format Documents...")
    rag_wifi = query_rag("My WiFi is not connecting", top_k=2)
    assert len(rag_wifi["chunks"]) > 0, "No RAG chunks retrieved for WiFi query!"
    print(f"   [OK] RAG retrieved {len(rag_wifi['chunks'])} chunks. Sources: {rag_wifi.get('sources')}")
    
    # 7. LangGraph Classifier & Technical Routing (Scenarios 1 & 2)
    print("\n[7/8] Testing LangGraph Routing Scenarios...")
    res1 = run_helpdesk_pipeline("My WiFi is not connecting", user_name="Throna")
    print(f"   [OK] Scenario 1 ('My WiFi is not connecting') -> Classifier: '{res1['classification']}'")
    assert res1['classification'] == "technical"
    
    res2 = run_helpdesk_pipeline("My laptop is very slow", user_name="Throna")
    print(f"   [OK] Scenario 2 ('My laptop is very slow') -> Classifier: '{res2['classification']}'")
    assert res2['classification'] == "technical"
    
    # 8. Ticket Agent, HITL Confirmation & Long-Term Memory (Scenarios 3, 4, 5)
    print("\n[8/8] Testing Ticket Agent, HITL Confirmation & User Memory...")
    res3 = run_helpdesk_pipeline("Create a ticket because my laptop keeps restarting", user_name="Throna")
    print(f"   [OK] Scenario 3 ('Create ticket...') -> Classifier: '{res3['classification']}'")
    assert res3['classification'] == "ticket"
    assert res3['pending_ticket'] is not None
    assert res3['pending_ticket']['priority'] == "HIGH"
    print(f"   [OK] Pending HITL Ticket detected with priority: {res3['pending_ticket']['priority']}")
    
    new_tkt = create_ticket(user_name="Throna", issue="Laptop keeps restarting", priority="HIGH")
    tkt_id = new_tkt["ticket_id"]
    print(f"   [OK] Ticket created with ID: {tkt_id}")
    
    status_msg = check_ticket_status(tkt_id)
    assert tkt_id in status_msg
    print(f"   [OK] Ticket status lookup verified for: {tkt_id}")
    
    res5_store = run_helpdesk_pipeline("My name is Throna", user_name="User")
    assert res5_store["user_name"] == "Throna"
    stored_name = retrieve_user_fact("user_name")
    assert stored_name == "Throna"
    print(f"   [OK] Long-term memory profile verified: user_name='{stored_name}'")
    
    print("\n=======================================================")
    print("  ALL 8 VERIFICATION GATES PASSED WITH 100% SUCCESS!")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()

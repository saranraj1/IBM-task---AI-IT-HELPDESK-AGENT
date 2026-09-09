import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

try:
    import torch
except Exception:
    pass

import html
import uuid
import streamlit as st
import datetime
from src.config import check_llm_status, DEFAULT_USER_NAME
from src.database import (
    get_ticket_stats,
    get_ticket,
    get_all_tickets,
    close_ticket as db_close_ticket,
    save_chat_message,
    get_chat_history,
    list_chat_sessions
)
from src.rag import get_indexed_chunk_count, reindex_knowledge_base
from src.tools import create_ticket, detect_priority
from src.graph import run_helpdesk_pipeline
from src.memory import retrieve_user_fact

# Page configuration
st.set_page_config(
    page_title="AI IT Helpdesk Command Center",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- LUXURY GLASSMORPHIC DESIGN SYSTEM -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

    /* Global Typography & Mesh Canvas */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: #070b14 !important;
        background-image: 
            radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.08) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(129, 140, 248, 0.07) 0px, transparent 50%),
            radial-gradient(at 50% 50%, rgba(15, 23, 42, 0.5) 0px, transparent 100%) !important;
        background-attachment: fixed !important;
        color: #f1f5f9 !important;
    }

    /* Animated Pulsing Beacon */
    @keyframes pulse-ring {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }
    @keyframes pulse-amber {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
    }

    /* Main Floating Header Banner */
    .hero-banner {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 16px;
        padding: 24px 30px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
    }
    .hero-title-group h1 {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0 0 6px 0;
        background: linear-gradient(135deg, #ffffff 10%, #38bdf8 55%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-title-group p {
        color: #94a3b8;
        font-size: 0.98rem;
        margin: 0;
        font-weight: 500;
    }
    .hero-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(56, 189, 248, 0.12);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.3);
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }

    /* Status Badges */
    .status-badge-cloud {
        background: rgba(56, 189, 248, 0.12);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.4);
        padding: 8px 16px;
        border-radius: 12px;
        font-size: 0.88rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 4px 14px rgba(56, 189, 248, 0.15);
    }
    .status-badge-cloud .dot {
        width: 8px;
        height: 8px;
        background: #38bdf8;
        border-radius: 50%;
        animation: pulse-ring 2s infinite;
    }
    .status-badge-ollama {
        background: rgba(34, 197, 94, 0.12);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.4);
        padding: 8px 16px;
        border-radius: 12px;
        font-size: 0.88rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 4px 14px rgba(34, 197, 94, 0.15);
    }
    .status-badge-ollama .dot {
        width: 8px;
        height: 8px;
        background: #22c55e;
        border-radius: 50%;
        animation: pulse-ring 2s infinite;
    }
    .status-badge-offline {
        background: rgba(245, 158, 11, 0.12);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
        padding: 8px 16px;
        border-radius: 12px;
        font-size: 0.88rem;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }
    .status-badge-offline .dot {
        width: 8px;
        height: 8px;
        background: #f59e0b;
        border-radius: 50%;
        animation: pulse-amber 2s infinite;
    }

    /* Streamlit Chat Messages Overhauls */
    [data-testid="stChatMessage"] {
        background: rgba(15, 23, 42, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(148, 163, 184, 0.12) !important;
        border-radius: 16px !important;
        padding: 18px 24px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25) !important;
        transition: transform 0.2s ease, border-color 0.2s ease !important;
    }
    [data-testid="stChatMessage"]:hover {
        border-color: rgba(56, 189, 248, 0.25) !important;
    }
    
    [data-testid="stChatMessageContent"] p,
    [data-testid="stMarkdownContainer"] p,
    .stMarkdown p {
        color: #e2e8f0 !important;
        font-size: 1.02rem !important;
        line-height: 1.7 !important;
        font-weight: 400 !important;
    }
    
    [data-testid="stChatMessageContent"] strong, 
    [data-testid="stMarkdownContainer"] strong,
    .stMarkdown strong {
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }

    [data-testid="stChatMessageContent"] code,
    [data-testid="stMarkdownContainer"] code {
        font-family: 'JetBrains Mono', monospace !important;
        background: rgba(15, 23, 42, 0.9) !important;
        color: #38bdf8 !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        padding: 3px 8px !important;
        border-radius: 6px !important;
        font-size: 0.88rem !important;
    }

    /* Ticket Card Styling */
    .ticket-glass-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.65) 0%, rgba(15, 23, 42, 0.85) 100%);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 14px;
        padding: 20px 24px;
        margin: 16px 0;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        position: relative;
        overflow: hidden;
    }
    .ticket-glass-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 6px;
        height: 100%;
    }
    .ticket-glass-card.high::before { background: linear-gradient(to bottom, #ef4444, #f87171); }
    .ticket-glass-card.medium::before { background: linear-gradient(to bottom, #f97316, #fb923c); }
    .ticket-glass-card.low::before { background: linear-gradient(to bottom, #10b981, #34d399); }
    
    .ticket-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
        padding-bottom: 10px;
    }
    .ticket-header h4 {
        margin: 0;
        color: #f8fafc !important;
        font-size: 1.15rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .priority-pill-high {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .priority-pill-medium {
        background: rgba(249, 115, 22, 0.15);
        color: #fb923c;
        border: 1px solid rgba(249, 115, 22, 0.4);
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .priority-pill-low {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    /* Sidebar Refinements */
    section[data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(148, 163, 184, 0.1) !important;
        padding-top: 10px;
    }
    .sidebar-brand {
        padding: 10px 0 16px 0;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }
    .sidebar-brand h2 {
        font-size: 1.3rem;
        font-weight: 800;
        margin: 0 0 4px 0;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .sidebar-brand p {
        font-size: 0.82rem;
        color: #64748b;
        margin: 0;
    }

    /* Metric Cards */
    .metric-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin: 12px 0;
    }
    .metric-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.3);
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
    }
    .metric-val.open { color: #38bdf8; }
    .metric-val.closed { color: #34d399; }
    .metric-lbl {
        font-size: 0.75rem;
        color: #94a3b8;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }

    /* Sidebar Buttons (Quick Action Chips) */
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(15, 23, 42, 0.8) !important;
        color: #cbd5e1 !important;
        border: 1px solid rgba(148, 163, 184, 0.15) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 8px 12px !important;
        text-align: left !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(56, 189, 248, 0.15) !important;
        color: #38bdf8 !important;
        border-color: rgba(56, 189, 248, 0.4) !important;
        transform: translateX(3px) !important;
    }

    /* Chat Input Styling */
    [data-testid="stChatInput"] {
        border-radius: 16px !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        background: rgba(15, 23, 42, 0.85) !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4) !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.3), 0 10px 25px rgba(0, 0, 0, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION INITIALIZATION -----------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

if "messages" not in st.session_state:
    db_history = get_chat_history(st.session_state.session_id)
    st.session_state.messages = db_history if db_history else []

if "pending_ticket" not in st.session_state:
    st.session_state.pending_ticket = None

if "user_name" not in st.session_state:
    saved_name = retrieve_user_fact("user_name")
    st.session_state.user_name = saved_name if saved_name else DEFAULT_USER_NAME

# Check Active Multi-Tier LLM Status
llm_info = check_llm_status()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <h2>🎧 IT Command Center</h2>
        <p>Autonomous Agentic IT Helpdesk Engine</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Live System Health Monitor
    st.subheader("System Health")
    if llm_info["active_tier"] == "cloud":
        m_name = html.escape(llm_info["cloud_model"])
        st.markdown(f'''
        <div class="status-badge-cloud">
            <div class="dot"></div>
            <span>☁️ Cloud: <strong>{m_name}</strong></span>
        </div>
        ''', unsafe_allow_html=True)
    elif llm_info["active_tier"] == "ollama":
        m_name = html.escape(llm_info["ollama_model"])
        st.markdown(f'''
        <div class="status-badge-ollama">
            <div class="dot"></div>
            <span>🖥️ Ollama: <strong>{m_name}</strong></span>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div class="status-badge-offline">
            <div class="dot"></div>
            <span>🟡 Offline RAG Mode</span>
        </div>
        ''', unsafe_allow_html=True)
        st.caption("No Cloud API key configured and Ollama offline. Falling back to Knowledge Base retrieval.")

    st.markdown("---")
    
    # Session Controls
    st.caption(f"Active Session: `{st.session_state.session_id}`")
    if st.button("➕ New Conversation", key="btn_new_chat", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.session_state.pending_ticket = None
        st.rerun()

    # Past Sessions Switcher
    past_sessions = list_chat_sessions(limit=8)
    if past_sessions:
        with st.expander("💬 Past Conversations", expanded=False):
            for ps in past_sessions:
                s_label = f"{ps['title'][:22]} ({ps['created_at'].split(' ')[0]})"
                if ps["session_id"] != st.session_state.session_id:
                    if st.button(f"📄 {s_label}", key=f"sess_{ps['session_id']}", use_container_width=True):
                        st.session_state.session_id = ps["session_id"]
                        st.session_state.messages = get_chat_history(ps["session_id"])
                        st.session_state.pending_ticket = None
                        st.rerun()

    st.markdown("---")

    # Quick Help Query Chips
    st.subheader("Quick Help Requests")
    suggested_queries = [
        ("🌐 WiFi Issues", "My WiFi is not connecting"),
        ("💻 Slow Laptop", "My laptop is very slow"),
        ("📧 Outlook Crash", "Outlook keeps crashing"),
        ("🔐 Password Reset", "I forgot my password"),
        ("🖨️ Printer Support", "My printer is not printing"),
        ("🛡️ VPN Failure", "My VPN is not connecting"),
        ("🚨 High Priority Ticket", "Create a ticket because my laptop keeps restarting")
    ]
    
    selected_query = None
    for label, q_text in suggested_queries:
        if st.button(label, key=f"btn_{q_text}", use_container_width=True):
            selected_query = q_text

    st.markdown("---")

    # Knowledge Base Metrics & Re-index
    st.subheader("Knowledge Base")
    chunk_cnt = get_indexed_chunk_count()
    st.info(f"📚 **{chunk_cnt} Chunks** indexed across `.txt` & `.md` guides")
    if st.button("🔄 Re-index Knowledge Base", key="btn_reindex_kb", use_container_width=True):
        with st.spinner("Re-indexing knowledge base documents..."):
            new_cnt = reindex_knowledge_base(force=True)
            st.toast(f"Knowledge Base successfully re-indexed! {new_cnt} chunks.")
            st.rerun()

    # Ticket Statistics Grid
    st.subheader("Support Metrics")
    stats = get_ticket_stats()
    st.markdown(f"""
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-val open">{stats["OPEN"]}</div>
            <div class="metric-lbl">Open Tickets</div>
        </div>
        <div class="metric-card">
            <div class="metric-val closed">{stats["CLOSED"]}</div>
            <div class="metric-lbl">Resolved</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Ticket Admin Management Section
    st.markdown("---")
    st.subheader("Ticket Admin")
    with st.expander("📋 View & Close Open Tickets", expanded=False):
        open_tkts = get_all_tickets(status="OPEN")
        if not open_tkts:
            st.caption("🟢 All tickets resolved. Queue is clear!")
        else:
            for ot in open_tkts:
                t_id_esc = html.escape(str(ot['ticket_id']))
                u_name_esc = html.escape(str(ot['user_name']))
                issue_esc = html.escape(str(ot['issue']))
                p_esc = html.escape(str(ot['priority']))
                
                st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.6); padding: 12px; border-radius: 8px; margin-bottom: 8px; border: 1px solid rgba(148, 163, 184, 0.1);">
                    <div style="display:flex; justify-content:space-between; margin-bottom: 6px;">
                        <span style="font-family:'JetBrains Mono'; color:#38bdf8; font-weight:700;">{t_id_esc}</span>
                        <span class="priority-pill-{p_esc.lower()}">{p_esc}</span>
                    </div>
                    <div style="font-size:0.88rem; color:#cbd5e1; margin-bottom: 4px;"><strong>User:</strong> {u_name_esc}</div>
                    <div style="font-size:0.85rem; color:#94a3b8;"><strong>Issue:</strong> {issue_esc}</div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"✅ Close Ticket {t_id_esc}", key=f"ui_close_{t_id_esc}", use_container_width=True):
                    db_close_ticket(ot['ticket_id'])
                    st.toast(f"Ticket {t_id_esc} successfully CLOSED!")
                    st.rerun()

# ----------------- MAIN UI -----------------
st.markdown("""
<div class="hero-banner">
    <div class="hero-title-group">
        <div class="hero-tag">⚡ Autonomous IT Support Specialist</div>
        <h1>AI IT Helpdesk Agent</h1>
        <p>Enterprise Troubleshooting, Intelligent Ticket Escalation & Retrieval-Augmented Memory</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Display Chat History with Sleek Ticket Cards & XSS Neutralization
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    
    with st.chat_message(role):
        st.markdown(content)
        # Render ticket cards if embedded in metadata
        if "ticket_card" in msg and msg["ticket_card"]:
            tkt = msg["ticket_card"]
            p_clean = html.escape(str(tkt.get('priority', 'LOW'))).upper()
            p_lower = p_clean.lower()
            t_id_clean = html.escape(str(tkt.get('ticket_id', '')))
            u_name_clean = html.escape(str(tkt.get('user_name', '')))
            issue_clean = html.escape(str(tkt.get('issue', '')))
            status_clean = html.escape(str(tkt.get('status', '')))
            created_clean = html.escape(str(tkt.get('created_at', '')))

            st.markdown(f"""
            <div class="ticket-glass-card {p_lower}">
                <div class="ticket-header">
                    <h4>🎫 Support Ticket Generated</h4>
                    <span class="priority-pill-{p_lower}">{p_clean} PRIORITY</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 10px;">
                    <div><span style="color:#94a3b8; font-size:0.8rem; text-transform:uppercase;">Ticket ID</span><br><code style="font-size:0.95rem; font-weight:700;">{t_id_clean}</code></div>
                    <div><span style="color:#94a3b8; font-size:0.8rem; text-transform:uppercase;">User</span><br><span style="font-weight:600; color:#f1f5f9;">{u_name_clean}</span></div>
                    <div><span style="color:#94a3b8; font-size:0.8rem; text-transform:uppercase;">Status</span><br><span style="color:#38bdf8; font-weight:700;">{status_clean}</span></div>
                    <div><span style="color:#94a3b8; font-size:0.8rem; text-transform:uppercase;">Created</span><br><span style="color:#94a3b8; font-size:0.9rem;">{created_clean}</span></div>
                </div>
                <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(148, 163, 184, 0.1);">
                    <span style="color:#94a3b8; font-size:0.8rem; text-transform:uppercase;">Reported Issue:</span>
                    <p style="margin: 4px 0 0 0; color:#e2e8f0; font-weight:500;">{issue_clean}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

# Handle Human-in-the-Loop Confirmation UI if pending ticket exists
if st.session_state.pending_ticket is not None:
    pending = st.session_state.pending_ticket
    p_clean = html.escape(str(pending.get('priority', 'HIGH'))).upper()
    p_lower = p_clean.lower()
    pending_issue_clean = html.escape(str(pending.get('issue', '')))
    
    with st.container():
        st.markdown(f"""
        <div class="ticket-glass-card {p_lower}" style="border: 1px solid rgba(245, 158, 11, 0.4); box-shadow: 0 0 25px rgba(245, 158, 11, 0.15);">
            <div class="ticket-header">
                <h4 style="color:#fbbf24 !important;">⚠️ Human-in-the-Loop Confirmation Required</h4>
                <span class="priority-pill-{p_lower}">{p_clean} PRIORITY DETECTED</span>
            </div>
            <p style="margin: 8px 0; color:#e2e8f0;">
                A critical IT issue requires escalating to a support ticket in the database.
            </p>
            <div style="background: rgba(15, 23, 42, 0.7); padding: 12px 16px; border-radius: 8px; margin: 12px 0;">
                <span style="color:#94a3b8; font-size:0.8rem; text-transform:uppercase;">Issue Summary:</span>
                <p style="margin: 4px 0 0 0; font-weight: 600; color: #f8fafc;">{pending_issue_clean}</p>
            </div>
            <p style="color:#94a3b8; font-size: 0.92rem; margin-bottom: 4px;">Would you like to record this ticket in SQLite?</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_yes, col_no = st.columns([1, 1])
        with col_yes:
            if st.button("✅ YES – Create Ticket", key="hitl_yes", type="primary", use_container_width=True):
                new_tkt = create_ticket(
                    user_name=pending["user_name"],
                    issue=pending["issue"],
                    priority=pending["priority"]
                )
                
                success_text = f"✅ **Ticket successfully created!**\nYour support ticket has been recorded with ID `{new_tkt['ticket_id']}`."
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": success_text,
                    "ticket_card": new_tkt
                })
                save_chat_message(st.session_state.session_id, "assistant", success_text, ticket_card=new_tkt)
                st.session_state.pending_ticket = None
                st.rerun()
                
        with col_no:
            if st.button("❌ NO – Cancel", key="hitl_no", use_container_width=True):
                cancel_msg = "🚫 Ticket creation request cancelled gracefully."
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": cancel_msg
                })
                save_chat_message(st.session_state.session_id, "assistant", cancel_msg)
                st.session_state.pending_ticket = None
                st.rerun()

# User Input Processing
user_input = st.chat_input("Ask an IT question or describe a technical problem...")

if selected_query:
    user_input = selected_query

if user_input and st.session_state.pending_ticket is None:
    # Append user message to state and SQLite
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_chat_message(st.session_state.session_id, "user", user_input)
    
    with st.spinner("Analyzing issue via LangGraph pipeline..."):
        res_state = run_helpdesk_pipeline(
            query=user_input,
            user_name=st.session_state.user_name,
            history=st.session_state.messages[:-1]
        )
        
        # Update user name if learned from pipeline
        if res_state.get("user_name"):
            st.session_state.user_name = res_state["user_name"]
            
        resp_content = res_state.get("response", "")
        
        # Check if pending ticket generated
        if res_state.get("pending_ticket"):
            st.session_state.pending_ticket = res_state["pending_ticket"]
            st.session_state.messages.append({
                "role": "assistant",
                "content": resp_content
            })
            save_chat_message(st.session_state.session_id, "assistant", resp_content)
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": resp_content
            })
            save_chat_message(st.session_state.session_id, "assistant", resp_content)
            
    st.rerun()

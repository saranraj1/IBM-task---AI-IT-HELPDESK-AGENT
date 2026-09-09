import re
import html
from src.config import (
    check_llm_status,
    check_ollama_status,
    LLM_PROVIDER,
    CLOUD_API_KEY,
    CLOUD_BASE_URL,
    CLOUD_MODEL,
    CLOUD_TIMEOUT_SECONDS,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    DEFAULT_MODEL,
    LLM_TEMPERATURE
)
from src.tools import detect_priority, check_ticket_status, create_ticket, get_current_time
from src.memory import extract_and_store_memories, retrieve_user_fact, format_all_user_memories

class CloudLLMWrapper:
    """Universal OpenAI-compatible Cloud LLM client (OpenAI, Groq, OpenRouter, etc.)."""
    def __init__(self, api_key: str, base_url: str, model: str, temperature: float = 0.0, timeout: int = 30):
        import openai
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.model = model
        self.temperature = temperature

    def invoke(self, prompt: str, system_prompt: str = None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        content = response.choices[0].message.content or ""
        
        class Result:
            def __init__(self, c):
                self.content = c
        return Result(content)

def get_cloud_llm():
    """Initializes Cloud LLM client if configured."""
    if not CLOUD_API_KEY:
        return None
    try:
        return CloudLLMWrapper(
            api_key=CLOUD_API_KEY,
            base_url=CLOUD_BASE_URL,
            model=CLOUD_MODEL,
            temperature=LLM_TEMPERATURE,
            timeout=CLOUD_TIMEOUT_SECONDS
        )
    except Exception as e:
        print(f"[LLM Warning] Cloud LLM initialization failed: {e}")
        return None

def get_ollama_llm():
    """Initializes local ChatOllama client."""
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=OLLAMA_MODEL, temperature=LLM_TEMPERATURE, base_url=OLLAMA_HOST)
    except Exception as e:
        print(f"[LLM Warning] Could not initialize ChatOllama: {e}")
        return None

def get_llm():
    """
    Tiered LLM getter:
    1. Returns Cloud LLM if configured and preferred
    2. Returns Ollama if running
    """
    if LLM_PROVIDER == "cloud" and CLOUD_API_KEY:
        cloud = get_cloud_llm()
        if cloud:
            return cloud
    return get_ollama_llm()

def execute_llm(prompt: str, system_prompt: str = None) -> tuple:
    """
    Executes prompt using Primary LLM (Cloud API) with automatic fallback to Secondary (Ollama).
    Returns tuple: (response_text, provider_used)
    """
    # 1. Attempt Cloud API if configured
    if CLOUD_API_KEY:
        try:
            cloud_llm = get_cloud_llm()
            if cloud_llm:
                res = cloud_llm.invoke(prompt, system_prompt=system_prompt)
                if res and res.content:
                    return (res.content.strip(), f"Cloud API ({CLOUD_MODEL})")
        except Exception as e:
            print(f"[LLM Fallback Notice] Primary Cloud API failed ({e}). Falling back to Secondary Ollama...")

    # 2. Attempt Local Ollama fallback
    ollama_info = check_ollama_status()
    if ollama_info["online"] and ollama_info["has_model"]:
        try:
            ollama_llm = get_ollama_llm()
            if ollama_llm:
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                res = ollama_llm.invoke(full_prompt)
                if res and res.content:
                    return (res.content.strip(), f"Local Ollama ({OLLAMA_MODEL})")
        except Exception as e:
            print(f"[LLM Warning] Secondary Ollama execution failed: {e}")

    return (None, "None (RAG Fallback)")

def classify_query(query: str) -> str:
    """
    Classifies an incoming user query into one of three categories:
    'technical' | 'ticket' | 'general'
    """
    text = query.lower().strip()
    
    # 1. Ticket patterns
    ticket_triggers = [
        "ticket", "tkt-", "support ticket", "open ticket", "create a ticket",
        "create ticket", "submit ticket", "check ticket", "ticket status"
    ]
    if any(tg in text for tg in ticket_triggers):
        return "ticket"
        
    # High priority issue direct ticket intent: e.g. "Create a ticket because my laptop keeps restarting"
    if "restarting" in text and ("create" in text or "ticket" in text or "restarts" in text):
        return "ticket"

    # 2. General / Memory patterns
    general_triggers = [
        "hello", "hi", "hey", "greetings", "good morning", "good afternoon",
        "my name is", "what is my name", "who am i", "remember", "time", "date",
        "what time", "thank you", "thanks", "bye"
    ]
    if any(text.startswith(gt) or gt in text for gt in general_triggers):
        if not any(tech_kw in text for tech_kw in ["wifi", "printer", "vpn", "outlook", "slow laptop"]):
            return "general"
            
    # 3. Technical patterns
    tech_keywords = [
        "wifi", "wi-fi", "internet", "connecting", "slow", "printer", "printing",
        "software", "crash", "crashing", "password", "forgot", "vpn", "email",
        "outlook", "laptop", "blue screen", "reboot", "network"
    ]
    if any(kw in text for kw in tech_keywords):
        return "technical"

    # 4. Try LLM classification with primary/secondary backend
    sys_prompt = "You are a classifier. Respond with ONLY one word: 'technical', 'ticket', or 'general'."
    prompt = f"Query: \"{query}\"\nCategory:"
    res_text, _ = execute_llm(prompt, system_prompt=sys_prompt)
    if res_text:
        res_lower = res_text.lower()
        for label in ["technical", "ticket", "general"]:
            if label in res_lower:
                return label

    return "general"

def run_classifier_node(state: dict) -> dict:
    """Classifier Node in LangGraph."""
    query = state.get("messages", [])[-1].get("content", "") if state.get("messages") else ""
    category = classify_query(query)
    state["classification"] = category
    return state

def run_technical_agent_node(state: dict) -> dict:
    """Technical Agent Node utilizing ChromaDB RAG and Multi-Tier LLM (Cloud -> Ollama -> RAG)."""
    messages = state.get("messages", [])
    query = messages[-1].get("content", "") if messages else ""
    
    # 1. RAG context retrieval
    from src.rag import query_rag
    rag_res = query_rag(query)
    context = rag_res.get("context", "")
    sources = rag_res.get("sources", [])
    state["retrieved_context"] = context
    
    # 2. Invoke LLM with Grounded System Instructions
    system_prompt = (
        "You are an expert IT Helpdesk Support Specialist.\n"
        "Follow these rules strictly:\n"
        "1. Use the provided troubleshooting documentation to solve the user's issue.\n"
        "2. Give concise, step-by-step instructions.\n"
        "3. Maintain a professional and reassuring tone."
    )
    user_prompt = (
        f"--- AUTHORITATIVE KNOWLEDGE BASE ---\n{context}\n\n"
        f"--- USER ISSUE ---\n{query}\n\n"
        f"Provide troubleshooting steps:"
    )
    
    response_text, provider = execute_llm(user_prompt, system_prompt=system_prompt)
    
    source_citation = f"\n\n📚 *Sources: {', '.join(sources)}*" if sources else ""
    provider_badge = f"\n\n*⚡ Answer generated by: {provider}*"
    
    if response_text:
        state["response"] = f"{response_text}{source_citation}{provider_badge}"
    else:
        # Graceful pure RAG fallback
        state["response"] = (
            f"🔧 **IT Support Troubleshooting Steps** (Retrieved directly from Knowledge Base):\n\n"
            f"{context}\n\n"
            f"*(Note: All LLM generation backends offline. Steps retrieved directly from vector store.)*{source_citation}"
        )

    return state

def run_ticket_agent_node(state: dict) -> dict:
    """Ticket Agent Node with Priority Detection and Human-in-the-Loop approval flags."""
    messages = state.get("messages", [])
    query = messages[-1].get("content", "") if messages else ""
    user_name = state.get("user_name", "User")
    query_lower = query.lower()
    
    # 1. List all open tickets
    if any(k in query_lower for k in ["list tickets", "all tickets", "show tickets", "view tickets", "open tickets"]):
        from src.tools import list_open_tickets
        state["response"] = list_open_tickets()
        state["pending_ticket"] = None
        return state

    # 2. Close a ticket
    if any(k in query_lower for k in ["close ticket", "resolve ticket", "mark closed", "close "]):
        tkt_match = re.search(r"[A-Z]{3,4}-\d{4}-\d{5}", query, re.IGNORECASE)
        if tkt_match:
            tkt_id = tkt_match.group(0).upper()
            from src.tools import close_ticket
            state["response"] = close_ticket(tkt_id)
            state["pending_ticket"] = None
            return state
        else:
            state["response"] = "Please specify the Ticket ID to close (e.g. `Close ticket TKT-2026-12345`)."
            state["pending_ticket"] = None
            return state

    # 3. Check specific ticket status
    tkt_match = re.search(r"[A-Z]{3,4}-\d{4}-\d{5}", query, re.IGNORECASE)
    if tkt_match or "check" in query_lower or "status" in query_lower:
        if tkt_match:
            tkt_id = tkt_match.group(0).upper()
            status_info = check_ticket_status(tkt_id)
            state["response"] = status_info
            state["pending_ticket"] = None
            return state
        elif "status" in query_lower and not ("create" in query_lower or "open" in query_lower):
            state["response"] = "Please provide your Ticket ID (e.g., TKT-2026-12345) to check its current status."
            state["pending_ticket"] = None
            return state

    # 4. Prepare pending ticket creation for Human-in-the-Loop Streamlit confirmation
    priority = detect_priority(query)
    pending_ticket = {
        "user_name": user_name,
        "issue": query,
        "priority": priority,
        "status": "PENDING_CONFIRMATION"
    }
    
    confirmation_msg = (
        f"I detected a **{priority}** priority issue.\n\n"
        f"**Issue Description:** {query}\n"
        f"**Detected Priority:** `{priority}`\n\n"
        f"Would you like me to submit this ticket into the IT database?"
    )
    
    state["pending_ticket"] = pending_ticket
    state["response"] = confirmation_msg
    return state

def run_general_agent_node(state: dict) -> dict:
    """General Agent Node handling small talk, time queries, profile memories, and LLM chat."""
    messages = state.get("messages", [])
    query = messages[-1].get("content", "") if messages else ""
    user_name = state.get("user_name", "User")
    query_lower = query.lower().strip()
    
    # 1. Store memory if user provides information
    learned_name = extract_and_store_memories(query)
    if learned_name:
        state["user_name"] = learned_name
        state["response"] = f"Nice to meet you, **{learned_name}**! I've saved your name in your long-term IT profile."
        return state
        
    # 2. Check if user asks "What is my name?" or "Who am I?"
    if "my name" in query_lower or "who am i" in query_lower:
        stored_name = retrieve_user_fact("user_name")
        if stored_name:
            state["user_name"] = stored_name
            state["response"] = f"Your name is **{stored_name}**, as recorded in your IT profile memory."
        else:
            state["response"] = "I don't have your name saved in profile memory yet. You can tell me by saying 'My name is [Your Name]'."
        return state

    # 3. Time / Date queries
    if "time" in query_lower or "date" in query_lower or "day" in query_lower:
        state["response"] = get_current_time()
        return state

    # 4. Multi-tier LLM Conversation with Long-Term Memory Profile
    memories_ctx = format_all_user_memories()
    system_prompt = (
        "You are a friendly, helpful IT Helpdesk virtual assistant.\n"
        f"User Profile Memory:\n{memories_ctx}"
    )
    res_text, provider = execute_llm(query, system_prompt=system_prompt)
    if res_text:
        state["response"] = res_text
        return state

    # Fallback greeting response when LLMs are offline
    if any(g in query_lower for g in ["hello", "hi", "hey"]):
        state["response"] = "Hello! How can I assist you with your IT equipment or support tickets today?"
    else:
        state["response"] = "I'm here to help with IT troubleshooting, password resets, Wi-Fi issues, software repairs, and support tickets."

    return state

import os
from pathlib import Path
import requests

try:
    from dotenv import load_dotenv
    # Search for .env in project root or current working dir
    base_dir = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=base_dir / ".env")
except ImportError:
    pass

# ------------------------------------------------------------------------------
# 1. PRIMARY LLM: Cloud API Configuration
# ------------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "cloud").strip().lower()
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", os.getenv("OPENAI_API_KEY", os.getenv("GROQ_API_KEY", ""))).strip()
CLOUD_BASE_URL = os.getenv("CLOUD_BASE_URL", "https://api.openai.com/v1").strip()
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gpt-4o-mini").strip()
CLOUD_TIMEOUT_SECONDS = int(os.getenv("CLOUD_TIMEOUT_SECONDS", "30"))

# ------------------------------------------------------------------------------
# 2. SECONDARY LLM: Local Ollama Configuration (Fallback)
# ------------------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", os.getenv("DEFAULT_MODEL", "llama3.2")).strip()
DEFAULT_MODEL = OLLAMA_MODEL  # Backward compatibility
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

# ------------------------------------------------------------------------------
# 3. Vector Store & RAG Configurations
# ------------------------------------------------------------------------------
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2").strip()
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu").strip()
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "it_helpdesk_kb").strip()
CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "data/chroma_db").strip()
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base").strip()
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# ------------------------------------------------------------------------------
# 4. Database & User Configurations
# ------------------------------------------------------------------------------
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/helpdesk.db").strip()
DEFAULT_USER_NAME = os.getenv("DEFAULT_USER_NAME", "User").strip()
TICKET_ID_PREFIX = os.getenv("TICKET_ID_PREFIX", "TKT").strip()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip()
APP_ENV = os.getenv("APP_ENV", "development").strip()


def check_ollama_status():
    """
    Checks if Ollama service is reachable and whether the target model is pulled.
    Returns dict: {'online': bool, 'has_model': bool, 'message': str, 'models': list}
    """
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            has_target = any(OLLAMA_MODEL in m for m in models)
            if has_target:
                return {
                    "online": True,
                    "has_model": True,
                    "message": f"Ollama is online with model '{OLLAMA_MODEL}'.",
                    "models": models
                }
            else:
                return {
                    "online": True,
                    "has_model": False,
                    "message": f"Ollama is running, but model '{OLLAMA_MODEL}' is missing. Run: ollama pull {OLLAMA_MODEL}",
                    "models": models
                }
    except Exception as e:
        return {
            "online": False,
            "has_model": False,
            "message": f"Ollama is not running. Please install Ollama and run: ollama pull {OLLAMA_MODEL}",
            "models": []
        }
    return {
        "online": False,
        "has_model": False,
        "message": "Unable to determine Ollama status.",
        "models": []
    }


def check_llm_status() -> dict:
    """
    Checks the multi-tier LLM system:
    1. Primary: Cloud API status (checks if API key is provided)
    2. Secondary: Ollama service reachability
    Returns status metadata for the UI and agent nodes.
    """
    cloud_ready = bool(CLOUD_API_KEY)
    ollama_status = check_ollama_status()
    ollama_ready = ollama_status["online"] and ollama_status["has_model"]

    # Determine active tier
    if LLM_PROVIDER == "cloud" and cloud_ready:
        active_tier = "cloud"
        summary_msg = f"Primary Cloud API active ({CLOUD_MODEL})."
    elif ollama_ready:
        active_tier = "ollama"
        if cloud_ready:
            summary_msg = f"Local Ollama active ({OLLAMA_MODEL})."
        else:
            summary_msg = f"Secondary Local Ollama active ({OLLAMA_MODEL}) [Cloud API key not set]."
    elif cloud_ready:
        # Fallback to cloud if provider set to ollama but ollama is offline
        active_tier = "cloud"
        summary_msg = f"Primary Cloud API active ({CLOUD_MODEL}) [Ollama offline]."
    else:
        active_tier = "offline"
        summary_msg = "All LLM backends offline. Running in direct Knowledge Base RAG mode."

    return {
        "primary_provider": LLM_PROVIDER,
        "active_tier": active_tier,
        "cloud_ready": cloud_ready,
        "cloud_model": CLOUD_MODEL,
        "cloud_base_url": CLOUD_BASE_URL,
        "ollama_online": ollama_status["online"],
        "ollama_has_model": ollama_status["has_model"],
        "ollama_model": OLLAMA_MODEL,
        "message": summary_msg
    }

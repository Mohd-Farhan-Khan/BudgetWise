"""
Configuration module for BudgetWise application.
Handles environment variables and configuration settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google API Configuration
def get_api_key():
    """Get the Google API key from environment variables.
    Prefer GEMINI_API_KEY, fall back to GOOGLE_API_KEY for compatibility.
    """
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

def validate_api_key():
    """Validate that API key is set and not the default placeholder"""
    api_key = get_api_key()
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        return False
    return True

# Database Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ACCESS_TOKEN_EXPIRES_HOURS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "24"))

# LangChain RAG Configuration
_default_index_dir = os.path.join(os.path.dirname(__file__), "langchain_store")
_env_index_dir = os.getenv("RAG_INDEX_DIR", _default_index_dir)
# Ensure absolute path regardless of current working directory
VECTOR_STORE_DIR = _env_index_dir if os.path.isabs(_env_index_dir) else os.path.abspath(os.path.join(os.path.dirname(__file__), _env_index_dir))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
# Use a local embedding model by default to avoid quota limits
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", os.getenv("GEMINI_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))

# Flask Configuration
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))
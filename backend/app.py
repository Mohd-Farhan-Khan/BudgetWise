from flask import Flask, request, jsonify
import logging
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
import bcrypt  # New dependency for password hashing
from werkzeug.security import check_password_hash  # Legacy verification only
from database import get_db_connection, init_db
from datetime import timedelta
import datetime
import mysql.connector
import os
# Import the new config module
from config import JWT_SECRET_KEY, JWT_ACCESS_TOKEN_EXPIRES_HOURS, FLASK_DEBUG, FLASK_PORT
# Import the new LangChain RAG implementation
import langchain_rag

# Logger
logger = logging.getLogger("api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = Flask(__name__)
# Configure CORS with explicit settings to handle preflight requests
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# JWT Configuration from config module
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRES_HOURS)
jwt = JWTManager(app)

# Validate required environment variables
if not app.config["JWT_SECRET_KEY"]:
    raise ValueError("JWT_SECRET_KEY environment variable is required")

# Initialize DB
init_db()

# --- Signup ---
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json or {}
    username = (data.get("username") or '').strip()
    email = (data.get("email") or '').strip().lower()
    password = data.get("password") or ''

    if not username or not email or not password:
        return jsonify({"message": "Missing required fields"}), 400

    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400

    # Hash password using bcrypt (store as utf-8 string). Legacy users keep PBKDF2 hashes.
    salt = bcrypt.gensalt(rounds=12)
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Check existing user by username OR email (accounting for legacy rows without email)
        cursor.execute("SELECT * FROM users WHERE username=%s OR email=%s", (username, email))
        existing = cursor.fetchone()
        if existing:
            return jsonify({"message": "User already exists"}), 409

        # Insert with email if column exists; fallback if migration not yet added
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_password))
        except mysql.connector.ProgrammingError:
            # email column absent (very early schema) -> add user without email
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        conn.commit()
        return jsonify({"message": "Signup successful"}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"message": "User already exists"}), 409
    except Exception as e:
        return jsonify({"message": "Signup failed", "error": str(e)}), 500
    finally:
        conn.close()

# --- Login ---
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        logger.warning("Login attempt with missing fields")
        return jsonify({"message": "Missing required fields"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        stored_hash = user["password"] or ""
        valid = False
        # Detect bcrypt hash prefixes
        if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                valid = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
            except ValueError:
                valid = False
        else:
            # Fallback to Werkzeug PBKDF2 check for legacy accounts
            try:
                valid = check_password_hash(stored_hash, password)
            except Exception:
                valid = False

        if valid:
            logger.info(f"Login successful for user_id={user['id']} username={user['username']}")
            access_token = create_access_token(identity=str(user["id"]))
            return jsonify({
                "message": "Login successful",
                "access_token": access_token,
                "user_id": user["id"],
                "username": user["username"],
                "email": user["email"]
            })
    logger.warning(f"Invalid login for username={username}")
    return jsonify({"message": "Invalid credentials"}), 401

# --- Add Expense ---
@app.route("/add_expense", methods=["POST"])
@jwt_required()
def add_expense():
    # get_jwt_identity returns the string we stored; convert back to int for DB use
    current_user_id = int(get_jwt_identity())
    data = request.json
    
    # Ensure the expense belongs to the authenticated user
    if "user_id" in data and int(data["user_id"]) != int(current_user_id):
        logger.warning(f"Unauthorized add_expense attempt by user_id={current_user_id} for user_id={data.get('user_id')}")
        return jsonify({"message": "Unauthorized to add expense for another user"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        logger.info(f"Adding expense for user_id={current_user_id} category={data.get('category')} amount={data.get('amount')} type={data.get('type')}")
        cursor.execute("""
            INSERT INTO expenses (user_id, date, category, note, amount, type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (current_user_id, data["date"], data["category"], data["note"], data["amount"], data["type"]))
        conn.commit()
        # Fetch the inserted row id and row for FAISS sync
        expense_id = cursor.lastrowid
        cursor.execute("SELECT id, user_id, date, category, note, amount, type FROM expenses WHERE id=%s", (expense_id,))
        row = cursor.fetchone()
        logger.info(f"Expense inserted id={expense_id}")
        
        # Update LangChain RAG index
        try:
            ok = langchain_rag.rag_service.add_transaction_to_index(row)
            logger.info(f"LangChain index update for expense_id={expense_id} ok={ok}")
        except Exception as e:
            # Do not fail API if indexing fails; log to console
            logger.exception(f"LangChain RAG indexing error for expense_id={expense_id}")
            
        return jsonify({"message": "Expense added successfully", "id": expense_id}), 201
    except Exception as e:
        logger.exception("Failed to add expense")
        return jsonify({"message": "Failed to add expense", "error": str(e)}), 400
    finally:
        conn.close()
# --- Legacy RAG Query Endpoint (redirects to LangChain) ---
@app.route("/chatbot/rag_query", methods=["POST"])
@jwt_required()
def rag_query():
    current_user_id = int(get_jwt_identity())
    payload = request.json or {}
    query = (payload.get("query") or "").strip()
    top_k = int(payload.get("top_k", 10))
    if not query:
        return jsonify({"message": "Query is required"}), 400

    try:
        # Redirect to LangChain implementation
        logger.info(f"Legacy RAG query redirected to LangChain user_id={current_user_id} top_k={top_k} query='{query[:80]}'")
        result = langchain_rag.rag_service.query_with_rag(
            user_id=current_user_id,
            query=query,
            top_k=top_k
        )
        logger.info(f"LangChain query answered matches={len(result.get('matches', []))}")
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Failed to run RAG query")
        return jsonify({"message": "Failed to run RAG query", "error": str(e)}), 500


# --- Legacy: Build/refresh FAISS index for the current user ---
@app.route("/chatbot/rag_build", methods=["POST"])  # idempotent
@jwt_required()
def rag_build():
    current_user_id = int(get_jwt_identity())
    try:
        # Redirect to LangChain implementation
        count = langchain_rag.rag_service.index_user_transactions(
            user_id=current_user_id,
            reindex=bool((request.json or {}).get("reindex", False))
        )
        return jsonify({"message": "Index built", "indexed": count}), 200
    except Exception as e:
        return jsonify({"message": "Failed to build index", "error": str(e)}), 500


# --- LangChain RAG Query Endpoint ---
@app.route("/chatbot/langchain/query", methods=["POST"])
@jwt_required()
def langchain_rag_query():
    current_user_id = int(get_jwt_identity())
    payload = request.json or {}
    query = (payload.get("query") or "").strip()
    top_k = int(payload.get("top_k", 10))
    
    if not query:
        return jsonify({"message": "Query is required"}), 400

    try:
        # Execute the full RAG pipeline with the LangChain implementation
        logger.info(f"LangChain RAG query user_id={current_user_id} top_k={top_k} query='{query[:80]}'")
        result = langchain_rag.rag_service.query_with_rag(
            user_id=current_user_id,
            query=query,
            top_k=top_k
        )
        logger.info(f"LangChain RAG query answered matches={len(result.get('matches', []))}")
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Failed to run LangChain RAG query")
        return jsonify({
            "message": "Failed to run LangChain RAG query",
            "error": str(e)
        }), 500


# --- LangChain: Build/refresh index for the current user ---
@app.route("/chatbot/langchain/build", methods=["POST"])
@jwt_required()
def langchain_rag_build():
    current_user_id = int(get_jwt_identity())
    payload = request.json or {}
    reindex = bool(payload.get("reindex", True))  # Default to True for better results
    
    try:
        logger.info(f"LangChain build request user_id={current_user_id} reindex={reindex}")
        # Index or reindex the user's transactions
        count = langchain_rag.rag_service.index_user_transactions(
            user_id=current_user_id,
            reindex=reindex
        )
        logger.info(f"LangChain build completed user_id={current_user_id} indexed_count={count}")
        return jsonify({
            "message": "LangChain index built successfully",
            "indexed": count
        }), 200
    except Exception as e:
        status = 500
        err_str = str(e)
        # Surface 429-like rate limit signals
        if "429" in err_str or "rate" in err_str.lower() or "exceed" in err_str.lower():
            status = 429
        logger.exception(f"LangChain build failed user_id={current_user_id} status={status}")
        return jsonify({
            "message": "Failed to build LangChain index",
            "error": err_str,
            "code": "rate_limited" if status == 429 else "index_failed"
        }), status


# --- LangChain: Get index statistics ---
@app.route("/chatbot/langchain/stats", methods=["GET"])
@jwt_required()
def langchain_rag_stats():
    try:
        stats = langchain_rag.rag_service.get_index_stats()
        logger.info(f"LangChain stats fetched total_docs={stats.get('total_documents',0)}")
        return jsonify(stats), 200
    except Exception as e:
        logger.exception("Failed to get index statistics")
        return jsonify({
            "message": "Failed to get index statistics",
            "error": str(e)
        }), 500

# --- LangChain: Clear conversation memory ---
@app.route("/chatbot/langchain/clear-memory", methods=["POST"])
@jwt_required()
def langchain_clear_memory():
    """Clear conversation memory for the current user."""
    current_user_id = int(get_jwt_identity())
    
    try:
        cleared = langchain_rag.rag_service.clear_conversation_memory(current_user_id)
        logger.info(f"Conversation memory clear request user_id={current_user_id} cleared={cleared}")
        
        if cleared:
            return jsonify({
                "message": "Conversation memory cleared successfully",
                "cleared": True
            }), 200
        else:
            return jsonify({
                "message": "No conversation memory to clear",
                "cleared": False
            }), 200
    except Exception as e:
        logger.exception(f"Failed to clear conversation memory for user_id={current_user_id}")
        return jsonify({
            "message": "Failed to clear conversation memory",
            "error": str(e)
        }), 500


# --- LangChain: Get conversation history ---
@app.route("/chatbot/langchain/history", methods=["GET"])
@jwt_required()
def langchain_get_history():
    """Get conversation history for the current user."""
    current_user_id = int(get_jwt_identity())
    
    try:
        history = langchain_rag.rag_service.get_conversation_history(current_user_id)
        logger.info(f"Conversation history request user_id={current_user_id} messages={len(history)}")
        
        return jsonify({
            "history": history,
            "message_count": len(history)
        }), 200
    except Exception as e:
        logger.exception(f"Failed to get conversation history for user_id={current_user_id}")
        return jsonify({
            "message": "Failed to get conversation history",
            "error": str(e)
        }), 500

# --- Get Expenses ---
@app.route("/expenses", methods=["GET"])
@jwt_required()
def get_expenses():
    current_user_id = int(get_jwt_identity())
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM expenses WHERE user_id=%s ORDER BY date DESC", (current_user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    # Convert date objects to string for JSON serialization
    for row in rows:
        if isinstance(row["date"], datetime.date):
            row["date"] = row["date"].isoformat()
    
    return jsonify(rows)

# --- Get User Info ---
@app.route("/user", methods=["GET"])
@jwt_required()
def get_user_info():
    current_user_id = int(get_jwt_identity())
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, email, created_at FROM users WHERE id=%s", (current_user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    return jsonify(user)

# --- DEBUG: list users (remove in production) ---
@app.route("/debug/users")
def debug_users():
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    try:
        c.execute("SELECT id, username, email FROM users ORDER BY id DESC LIMIT 20")
        return jsonify(c.fetchall())
    finally:
        conn.close()

# --- DEBUG: RAG status ---
@app.route("/debug/rag")
def debug_rag():
    try:
        stats = langchain_rag.rag_service.get_index_stats()
        return jsonify({
            "vector_store_present": bool(langchain_rag.rag_service.vector_store is not None),
            "vector_dir": langchain_rag.VECTOR_STORE_DIR if hasattr(langchain_rag, 'VECTOR_STORE_DIR') else "backend/langchain_store",
            "embedding_model": langchain_rag.EMBEDDING_MODEL if hasattr(langchain_rag, 'EMBEDDING_MODEL') else "models/embedding-001",
            "llm_model": langchain_rag.GEMINI_MODEL if hasattr(langchain_rag, 'GEMINI_MODEL') else "gemini-1.5-flash",
            "stats": stats
        }), 200
    except Exception as e:
        logger.exception("Failed debug_rag")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Use configuration from config module
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT, use_reloader=False)

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, init_db
from datetime import timedelta
import datetime
import mysql.connector

app = Flask(__name__)
CORS(app)

# JWT Configuration
app.config["JWT_SECRET_KEY"] = "your-secret-key"  # Change this in production!
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
jwt = JWTManager(app)

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

    hashed_password = generate_password_hash(password)

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
        return jsonify({"message": "Missing required fields"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user["password"], password):
        # Create access token. Cast identity to string to avoid PyJWT 422 "Subject must be a string" errors.
        access_token = create_access_token(identity=str(user["id"]))
        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "user_id": user["id"],
            "username": user["username"],
            "email": user["email"]
        })
    
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
        return jsonify({"message": "Unauthorized to add expense for another user"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO expenses (user_id, date, category, note, amount, type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (current_user_id, data["date"], data["category"], data["note"], data["amount"], data["type"]))
        conn.commit()
        return jsonify({"message": "Expense added successfully"}), 201
    except Exception as e:
        return jsonify({"message": "Failed to add expense", "error": str(e)}), 400
    finally:
        conn.close()

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

if __name__ == "__main__":
    # Use a non-conflicting port (5000 may be taken by macOS AirPlay Receiver)
    app.run(debug=True, port=5001, use_reloader=False)

# BudgetWise

> Personal finance tracker with a Flask + MySQL backend, LangChain-powered RAG financial insights, and a simple vanilla HTML/CSS/JS frontend (JWT auth, income/expense tracking, running balance, AI Q&A on your transactions).

## Features
- User signup & login (JWT auth – 24h expiry)
- Secure password hashing (bcrypt with Werkzeug fallback)
- MySQL persistence (users, expenses)
- Environment-based configuration (.env file)
- Add Income / Expense with category, note, date
- Transaction history & summary (Income / Expenses / Balance)
- CORS‑enabled API for local frontend
- Lightweight schema migration for added columns
- LangChain + Gemini-based Retrieval Augmented Generation (RAG) over your transactions
  - Build a per‑user financial vector index
  - Ask natural language questions ("How much did I spend on groceries in August?", "What are my top categories this month?")
  - Out‑of‑scope guardrails (won't answer unrelated questions)

## Tech Stack
Backend: Flask, flask-jwt-extended, mysql-connector-python, bcrypt, python-dotenv, LangChain, FAISS, sentence-transformers, Google Generative AI (Gemini)  
Frontend: HTML, CSS, vanilla JS  
DB: MySQL  
AI: Local sentence-transformers embeddings + Gemini model for generation

> Note: `backend/routes.py` (FastAPI style) exists but is **not wired in**. Runtime uses `backend/app.py`.
> Legacy RAG endpoints (`/chatbot/rag_*`) transparently call the LangChain implementation; prefer `/chatbot/langchain/*`.

## Structure
```
backend/
  app.py               # Flask app (port 5001) + RAG endpoints
  database.py          # DB connection + mini migrations
  langchain_rag.py     # LangChain RAG service (vector store + QA)
  langchain_store/     # Auto-generated FAISS index & metadata (ignored)
  models.sql           # Reference schema
  forecast.py          # Placeholder
  routes.py            # Unused FastAPI router
  config.py            # Centralized config/env parsing
  requirements.txt
  .env                 # Environment variables (not in git)
  .env.example         # Environment template
frontend/
  index.html           # Dashboard (protected)
  login.html           # Login
  signup.html          # Signup
  dashboard.js         # Auth + expense logic
  langchain-chat.js    # Frontend integration for LangChain RAG
  rag-chat.js          # Legacy placeholder (no-op)
  style.css
budgetwise_env/        # Local venv (ignored)
```

## Prerequisites
Python 3.12+, MySQL server. Port 5000 may be used by macOS AirPlay; app runs on 5001.

## Quick Start

### 1. Set up Python Environment
```bash
python3 -m venv budgetwise_env
source budgetwise_env/bin/activate
pip install -r backend/requirements.txt
```

### 2. Configure Environment Variables
```bash
# Copy the example file and edit with your values
cp backend/.env.example backend/.env

# Edit backend/.env with your database credentials:
# DB_HOST=localhost
# DB_USER=root
# DB_PASSWORD=your_mysql_password
# DB_NAME=budgetwise
# JWT_SECRET_KEY=generate-a-strong-secret-key
# JWT_ACCESS_TOKEN_EXPIRES_HOURS=24
# FLASK_DEBUG=True
# FLASK_PORT=5001
# GEMINI_API_KEY=your_gemini_api_key              # or GOOGLE_API_KEY for compatibility
# GEMINI_MODEL=gemini-1.5-flash                   # optional override
# EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2  # override if desired
# RAG_INDEX_DIR=./backend/langchain_store         # optional custom path (will be absolutized)
```

**Important:** Generate a strong JWT secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Start the Application
```bash
python backend/app.py   # http://127.0.0.1:5001

# Serve frontend (optionally):
python -m http.server 5500
# Open http://127.0.0.1:5500/frontend/signup.html
```

## Schema
```
users(id, username, email, password, created_at)
expenses(id, user_id, date, category, note, amount, type['Income'|'Expense'])
```
`database.init_db()` creates/migrates missing columns.

## API
| Method | Path                        | Auth | Notes |
|--------|-----------------------------|------|-------|
| POST   | /signup                     | No   | Create user |
| POST   | /login                      | No   | Returns JWT + user info |
| POST   | /add_expense                | Yes  | Add expense/income (auto-indexes in RAG) |
| GET    | /expenses                   | Yes  | List user expenses |
| GET    | /user                       | Yes  | User profile |
| GET    | /debug/users                | No   | Recent users (dev) |
| POST   | /chatbot/langchain/build    | Yes  | Build (or re/build) vector index for user |
| GET    | /chatbot/langchain/stats    | Yes  | Index statistics |
| POST   | /chatbot/langchain/query    | Yes  | Ask financial question (RAG) |
| POST   | /chatbot/rag_build          | Yes  | Legacy alias → LangChain build |
| POST   | /chatbot/rag_query          | Yes  | Legacy alias → LangChain query |
| GET    | /debug/rag                  | No   | Debug RAG status (dev) |

Header for protected routes:
```
Authorization: Bearer <token>
```

## Frontend Flow
1. Signup / login → store token + user metadata in localStorage.
2. Dashboard loads → validates token → fetches `/expenses`.
3. (Optional) Build RAG index: click "Build Index" (calls `/chatbot/langchain/build`).
4. Ask questions in chat: sends `/chatbot/langchain/query`.
5. Add transaction → POST `/add_expense` → auto-added to vector index.

### RAG Usage Quickstart
1. Ensure `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) is set in `.env`.
2. Run backend and login.
3. Click Build Index (or call API):
```bash
curl -X POST http://127.0.0.1:5001/chatbot/langchain/build \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"reindex": true}'
```
4. Ask a question:
```bash
curl -X POST http://127.0.0.1:5001/chatbot/langchain/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "How much did I spend on food this month?", "top_k": 8}'
```
5. View stats:
```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:5001/chatbot/langchain/stats
```

If you ask something unrelated (e.g. "Tell me a joke"), the model will respond with a scope-guard message.

## Common Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| 422 Subject must be a string | Old JWT issued before identity cast | Log out & log back in |
| 403 / odd headers on :5000   | macOS AirPlay took port 5000         | Use 5001 (already set) |
| "Server error" on signup     | Frontend hitting wrong port          | Hard refresh (Cmd+Shift+R) |
| 500 / RAG build fails        | Missing or invalid GEMINI_API_KEY    | Set key & restart |
| 429 on build/query           | Upstream rate limit (Gemini API)     | Wait ~20s and retry |
| Empty RAG answers            | Index not built / no transactions    | Build index after adding data |

## Improvements To Do
- Add edit/delete for expenses
- Pagination & filtering
- Hook up forecasting prototype
- Add tests (pytest) & linting
- Make frontend API URL configurable
- Add input validation and better error surfaces
- Per-user isolated vector stores or filtering improvements
- Rate limit & caching strategy for RAG

## Contributing
Small PRs welcome. Clean code, clear commit messages.

## Disclaimer
Development project – not production hardened.

Happy budgeting & querying! 🧮🤖

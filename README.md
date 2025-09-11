# BudgetWise

> Personal finance tracker with a Flask + MySQL backend and a simple vanilla HTML/CSS/JS frontend (JWT auth, income/expense tracking, running balance).

## Features
- User signup & login (JWT auth – 24h expiry)
- Secure password hashing (Werkzeug)
- MySQL persistence (users, expenses)
- Add Income / Expense with category, note, date
- Transaction history & summary (Income / Expenses / Balance)
- CORS‑enabled API for local frontend
- Lightweight schema migration for added columns

## Tech Stack
Backend: Flask, flask-jwt-extended, mysql-connector-python  
Frontend: HTML, CSS, vanilla JS  
DB: MySQL

> Note: `backend/routes.py` (FastAPI style) exists but is **not wired in**. Runtime uses `backend/app.py`.

## Structure
```
backend/
  app.py              # Flask app (port 5001)
  database.py         # DB connection + mini migrations
  models.sql          # Reference schema
  forecast.py         # Placeholder
  routes.py           # Unused FastAPI router
  requirements.txt
frontend/
  index.html          # Dashboard (protected)
  login.html          # Login
  signup.html         # Signup
  dashboard.js        # Auth + expense logic
  style.css
budgetwise_env/       # Local venv (ignore)
```

## Prerequisites
Python 3.12+, MySQL server. Port 5000 may be used by macOS AirPlay; app runs on 5001.

## Quick Start
```bash
python3 -m venv budgetwise_env
source budgetwise_env/bin/activate
pip install -r backend/requirements.txt

# (Optional) env vars instead of hard-coded secrets
export BUDGETWISE_DB_HOST=localhost
export BUDGETWISE_DB_USER=root
export BUDGETWISE_DB_PASSWORD=your_password
export BUDGETWISE_DB_NAME=budgetwise
export BUDGETWISE_JWT_SECRET=change-me

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
| Method | Path         | Auth | Notes |
|--------|--------------|------|-------|
| POST   | /signup      | No   | Create user |
| POST   | /login       | No   | Returns JWT + user info |
| POST   | /add_expense | Yes  | Add expense/income |
| GET    | /expenses    | Yes  | List user expenses |
| GET    | /user        | Yes  | User profile |
| GET    | /debug/users | No   | Recent users (dev) |

Header for protected routes:
```
Authorization: Bearer <token>
```

## Frontend Flow
1. Signup / login → store token + user metadata in localStorage.
2. Dashboard loads → validates token → fetches `/expenses`.
3. Add transaction → POST `/add_expense` → refresh list.

## Common Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| 422 Subject must be a string | Old JWT issued before identity cast | Log out & log back in |
| 403 / odd headers on :5000   | macOS AirPlay took port 5000         | Use 5001 (already set) |
| "Server error" on signup     | Frontend hitting wrong port          | Hard refresh (Cmd+Shift+R) |

## Improvements To Do
- Move secrets to env vars (see Config section)
- Add edit/delete for expenses
- Pagination & filtering
- Hook up forecasting prototype
- Add tests (pytest) & linting

## Contributing
Small PRs welcome. Clean code, clear commit messages.

## Disclaimer
Development project – not production hardened.

Happy budgeting!

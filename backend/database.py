import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "budgetwise")
    )
    return conn

def _migrate_users_table(cursor):
    """Ensure the users table has expected columns (email, created_at)."""
    cursor.execute("SHOW TABLES LIKE 'users'")
    if not cursor.fetchone():
        # Table does not exist yet; creation handled in init_db
        return
    cursor.execute("SHOW COLUMNS FROM users")
    existing_cols = {row[0] for row in cursor.fetchall()}
    # Add email column if missing (nullable first to avoid failure on existing rows)
    if 'email' not in existing_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE NULL AFTER username")
    # Add created_at if missing
    if 'created_at' not in existing_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Users table if not exists (legacy instances may lack email / created_at)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
        """
    )

    # Run lightweight migrations to add new columns when upgrading
    _migrate_users_table(cursor)

    # Create Expenses table (add created_at if desired, but remain compatible with existing)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            date DATE,
            category VARCHAR(255),
            note TEXT,
            amount DECIMAL(10,2),
            type ENUM('Income', 'Expense'),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()

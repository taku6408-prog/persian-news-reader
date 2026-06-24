
import os
import psycopg2
from dotenv import load_dotenv

def fix_schema():
    load_dotenv()
    dsn = {
        "host":     os.getenv("DB_HOST"),
        "port":     os.getenv("DB_PORT"),
        "dbname":   os.getenv("DB_NAME"),
        "user":     os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "sslmode":  "require"
    }
    
    try:
        conn = psycopg2.connect(**dsn)
        conn.autocommit = True
        cur = conn.cursor()
        print("Updating guid column to TEXT...")
        cur.execute("ALTER TABLE articles ALTER COLUMN guid TYPE TEXT;")
        print("Success!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_schema()

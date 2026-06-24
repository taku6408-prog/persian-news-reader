
import os
import psycopg2
from dotenv import load_dotenv

def test_connection():
    load_dotenv()
    
    dsn = {
        "host":     os.getenv("DB_HOST"),
        "port":     os.getenv("DB_PORT"),
        "dbname":   os.getenv("DB_NAME"),
        "user":     os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "sslmode":  "require"  # Supabase requires SSL
    }
    
    print(f"Connecting to {dsn['host']}...")
    try:
        conn = psycopg2.connect(**dsn)
        print("Successfully connected to Supabase!")
        
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"PostgreSQL version: {version[0]}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    # Connect to database
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()

    print("✅ Connected to database\n")

    # List all tables in public schema
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables = cur.fetchall()
    print("📌 Tables in your database:")
    for t in tables:
        print("-", t[0])

    # For each table, list columns
    for t in tables:
        table_name = t[0]
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}';")
        cols = cur.fetchall()
        print(f"\n📊 Columns in table '{table_name}':")
        for c in cols:
            print("-", c[0], ":", c[1])

    cur.close()
    conn.close()

except Exception as e:
    print("❌ Error:", e)

import os
import psycopg2
from dotenv import load_dotenv
from groq import Groq

# -------------------- Load environment variables --------------------
load_dotenv()

# -------------------- Database Connection --------------------
try:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()
    print("✅ Connected to database")
except Exception as e:
    print(f"❌ Database connection error: {e}")
    exit()

# -------------------- LLaMA Client --------------------
try:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except Exception as e:
    print(f"❌ LLaMA client error: {e}")
    exit()

# -------------------- Prompt Template --------------------
STRICT_PROMPT = """
You are a hospital assistant chatbot connected to a database of hospitals, doctors, and beds.

Reply formats:

1. Requirement satisfied:
Yes, {Hospital Name} has a {Specialty} specialist available.
Doctor: {Doctor Name}
Specialty: {Specialty}
Experience: {X years}
Location: {Area/Location}
Beds Available: {Count}

2. Requirement not available:
No {Specialty} specialist is available at {Hospital Name}.
👉 Alternative {Specialty} doctors are available at:
{Other Hospital} – {Doctor Name} ({Specialty}, {X years}, {Location})

3. Doctor mismatch:
Sorry, {Doctor Name} is not listed in {Hospital Name}.
👉 Available {Specialty} specialists at {Hospital Name} include:
Dr. {Name} ({Specialty}, {X years} experience)

Always follow these exact structures. Never deviate.
"""

# -------------------- Fetch Context --------------------
def fetch_context():
    cur.execute("""
        SELECT h.hospital_name, h.location, h.area,
               d.doctor_name, d.specialty, d.experience_years, d.availability,
               h.available_beds
        FROM hospitals h
        JOIN doctors d ON h.hospital_id = d.hospital_id
        ORDER BY h.hospital_id, d.experience_years DESC;
    """)
    rows = cur.fetchall()
    if not rows:
        return "Database is empty."

    context = ""
    for row in rows:
        hospital, loc, area, doc, spec, exp, avail, beds = row
        status = "Available" if avail else "Not Available"
        context += (f"- {hospital} ({area}, {loc}): Dr. {doc}, {spec}, "
                    f"{exp} yrs, {status}, Beds: {beds}\n")
    return context

# -------------------- Chat Function --------------------
def ask_llama(user_query):
    context = fetch_context()
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  
            messages=[
                {"role": "system", "content": STRICT_PROMPT},
                {"role": "user", "content": f"DB Data:\n{context}\nUser Query: {user_query}"}
            ],
            temperature=0.0,
            max_tokens=400
        )
        # ✅ FIX: Use dot notation, not subscript
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ LLaMA error: {e}"

# -------------------- Main Loop --------------------
if __name__ == "__main__":
    while True:
        q = input("\nEnter your query (or 'exit'): ")
        if q.lower() == "exit":
            break
        print("\nChatbot Reply:\n", ask_llama(q))

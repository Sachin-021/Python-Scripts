import os
import psycopg2
from groq import Groq
from dotenv import load_dotenv
import json
from rapidfuzz import process

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
except Exception as e:
    print("Database connection error:", e)
    exit()

# -------------------- Groq Client --------------------
client = Groq(api_key=os.getenv("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"))  # keep in .env

# -------------------- Utility: Fuzzy Matching --------------------
def fuzzy_match(input_str, choices, threshold=80):
    """Return best fuzzy match from choices if score >= threshold."""
    if not input_str or not choices:
        return None
    match = process.extractOne(input_str, choices)
    if match and match[1] >= threshold:
        return match[0]
    return None

# -------------------- User Input (Runtime) --------------------
user_input = input("Enter your query: ")

# -------------------- Step 1: Extract Metadata --------------------
prompt_metadata = f"""
You are a medical query parser. 
Your task is to extract structured metadata from noisy or imperfect user queries.

User query: "{user_input}"

Return ONLY a valid JSON object with EXACTLY these fields:
- intent: "find_doctor", "check_beds", "greet", "other"
- symptom: (health issue if any, else "")
- specialty: (medical specialty if clear or can be inferred, else "")
- hospital_name: (hospital requested if any, tolerate spelling mistakes, else "")
- doctor_name: (doctor requested if any, tolerate spelling mistakes, else "")

Rules:
1. Always output valid JSON (no extra text).
2. Normalize common typos (e.g., "Apolo" → "Apollo").
3. Infer specialty from symptom if possible (e.g., "bone pain" → "Orthopedics").
4. If hospital or doctor not clearly mentioned, leave as "".
5. If the query is just a greeting, set intent = "greet".

Example:
{{
  "intent": "find_doctor",
  "symptom": "bone pain",
  "specialty": "Orthopedics",
  "hospital_name": "Coimbatore Medical Center",
  "doctor_name": ""
}}
"""

try:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt_metadata}],
        temperature=0.1
    )
    metadata_str = response.choices[0].message.content.strip()
    metadata = json.loads(metadata_str)
except Exception as e:
    print("Error extracting metadata:", e)
    metadata = {}

user_symptom = metadata.get("symptom", "").lower()
user_specialty = metadata.get("specialty", "").title()
user_hospital = metadata.get("hospital_name", None)
user_doctor = metadata.get("doctor_name", None)

# -------------------- Step 2: Symptom → Specialty Mapping --------------------
specialty_map = {
    "chest pain": "Cardiology",
    "heart problem": "Cardiology",
    "fracture": "Orthopedics",
    "bone pain": "Orthopedics",
    "eye problem": "Ophthalmology",
    "vision issue": "Ophthalmology",
    "stomach pain": "Gastroenterology",
    "skin rash": "Dermatology",
    "pregnancy": "Gynecology",
    "fever": "General Medicine"
}
specialty = user_specialty or specialty_map.get(user_symptom, None)

# -------------------- Step 3: Apply Fuzzy Matching --------------------
# Hospitals list
cur.execute("SELECT hospital_name FROM hospitals;")
all_hospitals = [r[0] for r in cur.fetchall()]
user_hospital = fuzzy_match(user_hospital, all_hospitals) or user_hospital

# Specialties list
cur.execute("SELECT DISTINCT specialty FROM doctors;")
all_specialties = [r[0] for r in cur.fetchall()]
specialty = fuzzy_match(specialty, all_specialties) or specialty

# Doctors list (optional fuzzy match if user specifies)
if user_doctor:
    cur.execute("SELECT doctor_name FROM doctors;")
    all_doctors = [r[0] for r in cur.fetchall()]
    user_doctor = fuzzy_match(user_doctor, all_doctors) or user_doctor

# -------------------- Step 4: Query Database --------------------
def get_doctors(symptom=None, specialty=None, hospital=None, location="Coimbatore"):
    base_query = """
    SELECT h.hospital_name, h.area, d.doctor_name, d.specialty, d.experience_years, h.available_beds
    FROM hospitals h
    JOIN doctors d ON h.hospital_id = d.hospital_id
    WHERE d.availability = TRUE
      AND h.available_beds > 0
    """
    params = []

    # Location filter
    if location:
        base_query += " AND h.location = %s"
        params.append(location)

    # Specialty filter
    if specialty:
        base_query += " AND d.specialty = %s"
        params.append(specialty)

    # Hospital filter
    if hospital:
        base_query += " AND LOWER(h.hospital_name) = LOWER(%s)"
        params.append(hospital)

    # Doctor filter
    if user_doctor:
        base_query += " AND LOWER(d.doctor_name) = LOWER(%s)"
        params.append(user_doctor)

    # Ordering
    base_query += """
    ORDER BY 
        CASE WHEN %s IS NOT NULL AND LOWER(h.hospital_name) = LOWER(%s) THEN 0 ELSE 1 END,
        d.experience_years DESC,
        h.available_beds DESC
    LIMIT 5;
    """
    params.extend([hospital, hospital])

    cur.execute(base_query, tuple(params))
    results = [
        {
            "hospital_name": r[0],
            "area": r[1],
            "doctor_name": r[2],
            "specialty": r[3],
            "experience": r[4],
            "available_beds": r[5]
        }
        for r in cur.fetchall()
    ]
    return results

results = get_doctors(symptom=user_symptom, specialty=specialty, hospital=user_hospital)

# -------------------- Step 5: Format Doctor Info --------------------
def format_doctor(doctor):
    return (f"Dr. {doctor['doctor_name']} ({doctor['specialty']}, {doctor['experience']} yrs) "
            f"at {doctor['hospital_name']} ({doctor['area']}) — Beds available: {doctor['available_beds']}")

if results:
    primary_doctor = results[0]
    other_doctors = results[1:]
else:
    primary_doctor = None
    other_doctors = []

# -------------------- Step 6: Generate Final Chatbot Reply --------------------
friendly_prompt = f"""
You are a hospital recommendation assistant.

User query: "{user_input}"

Doctors retrieved from database:
Primary Doctor:
{format_doctor(primary_doctor) if primary_doctor else "None"}
Alternative Options:
{chr(10).join([format_doctor(d) for d in other_doctors]) or "None"}

Instructions:
1. If a specific hospital was requested, prioritize recommending from that hospital first.
2. If no doctor available in that hospital, politely say so and suggest alternatives nearby.
3. Always mention: Doctor Name, Specialty, Experience (yrs), Hospital, Area, Available Beds.
4. Keep the tone: friendly, professional, unbiased.
5. Structure output as:

**Recommended Doctor**
- (doctor details)

**Alternative Options**
- (doctor details)
"""

try:
    reply = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": friendly_prompt}],
        temperature=0.4
    )
    print("\nChatbot Reply:\n", reply.choices[0].message.content)
except Exception as e:
    print("Error generating chatbot reply:", e)

# -------------------- Cleanup --------------------
cur.close()
conn.close()

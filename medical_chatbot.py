import os
import psycopg2
import json
import re
from dotenv import load_dotenv
from groq import Groq
from thefuzz import process
import psycopg2.extras


# -------------------- Load Environment Variables --------------------
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# -------------------- Prompt Template --------------------
SYSTEM_PROMPT = """
You are a hospital-doctor information assistant.  
Your job is to convert user questions into SQL queries, execute them, and then return a polite natural-language answer. 

You must follow these rules strictly:

1. Input: User will ask about hospitals, doctors, symptoms, specialties, beds, or availability.
2. Output: You MUST return ONLY a valid SQL query (no explanations, no natural text).
3. Always query using ONLY these tables:
   - hospital_doctor_data(hospital_name, area, doctor_name, specialty, experience_years, availability, available_beds)
   - symptom_specialty(symptom_keyword, specialty)
4. Do not invent or assume data. If input is unclear, make the best SQL guess.
5. Never respond with plain text. Always output SQL only

--------------------
DATABASE SCHEMA
--------------------
Table: hospital_doctor_data
    - hospital_name TEXT
    - area TEXT
    - doctor_name TEXT
    - specialty TEXT
    - experience_years INT
    - availability TEXT
    - available_beds INT

Table: symptom_specialty
    - symptom_keyword TEXT
    - specialty TEXT

1. You MUST use these table names exactly and without typos:
   - hospital_doctor_data
   - symptom_specialty

2. Do NOT invent, shorten, change or misspell any table or column names.

3. When querying for doctors at a hospital, ensure the SQL looks like:
   SELECT doctor_name, specialty, experience_years, availability FROM hospital_doctor_data WHERE hospital_name = '<hospital_name>' LIMIT 3;

4. Always limit results to max 3 rows.


--------------------
TASK
--------------------
1. Understand user query and map it to SQL using ONLY the above tables.  
2. Execute the SQL query (hidden from the user).  
3. Convert results into polite natural-language output.  
   - Always show matching doctor(s) with hospital name, specialty, and years of experience.  
   - If hospital is given → return doctors in that hospital.  
   - If doctor is given → return doctor info with hospital and specialty.  
   - If symptom is given → map it to specialty using `symptom_specialty`, then show matching doctors/hospitals.  
   - If both hospital and doctor are given → filter on both.  
   - If no exact match, politely say so and suggest the closest available doctors/hospitals.  
   - Limit results to max 3.  
4. Never reveal SQL, schema, or raw data. Only return formatted text.  

--------------------
RULES
--------------------
- Always mention the **best matching doctor first**.  
- Provide 1–2 **secondary suggestions** when possible.  
- If hospital is asked, also mention available beds.  
- Keep responses short, polite, and professional.  

--------------------
OUTPUT FORMAT
--------------------
Examples:

Example 1 (Doctor query):  
"Dr. Varun Iyer is available at Fortis Health Center for Cardiology (25 years of experience). Another option is Dr. Anand Krishnan at Aravind Eye Hospital."

Example 2 (Hospital query):  
"Apollo Hospital currently has 20 available beds and Dr. Meena Raghavan (Neurology, 18 years experience). You could also consider Fortis Health Center for similar care."

Example 3 (Symptom query):  
"For fever, I found Dr. Ravi Sharma (General Medicine, Apollo Hospital, 15 years experience). Alternatively, Dr. Priya Nair at Fortis Health Center is also available."

Example (Hospital-only query):
"List doctors working at Shree Balaji Medical Institute"
SQL:
SELECT doctor_name, specialty, experience_years, availability FROM hospital_doctor_data WHERE hospital_name = 'Shree Balaji Medical Institute' LIMIT 3;


"""

# -------------------- Helpers --------------------
def extract_sql(text: str):
    """Extract SQL query safely from JSON response"""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == -1:
            return None
        data = json.loads(text[start:end])
        return data.get("sql")
    except Exception:
        return None


def normalize_input(user_query: str) -> str:
    """Clean up messy user input for better matching"""
    text = user_query.lower()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace("’", "'").replace("''", "'")
    return text.strip()


def ask_llama(user_query: str) -> str:
    """Send user query to Groq (LLaMA) and return response"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        temperature=0  # deterministic SQL
    )
    return response.choices[0].message.content


def fuzzy_match(user_input, column_values):
    """Fuzzy match user input to closest column value"""
    best_match = process.extractOne(user_input, column_values)
    return best_match[0] if best_match else user_input


def format_results(results, query_type="doctor"):
    """
    Format SQL query results into a polite natural language response.
    Includes doctor availability.
    """
    if not results or len(results) == 0:
        return "❌ I could not find an exact match. Please try with another hospital, doctor, or symptom."

    response = []

    # Handle doctor-related results
    if query_type == "doctor":
        for row in results[:3]:  # Limit to top 3
            doctor_name = row.get("doctor_name", "Unknown Doctor")
            hospital_name = row.get("hospital_name", "Unknown Hospital")
            specialty = row.get("specialty", "Unknown Specialty")
            experience = row.get("experience_years", "N/A")
            availability = row.get("availability", "Availability not listed")

            response.append(
                f"🩺 Dr. {doctor_name} ({specialty}, {experience} years experience) "
                f"is available at {hospital_name}. Current status: {availability}."
            )

    # Handle hospital-related results
    elif query_type == "hospital":
        for row in results[:3]:
            hospital_name = row.get("hospital_name", "Unknown Hospital")
            available_beds = row.get("available_beds", "N/A")
            specialty = row.get("specialty", "Unknown Specialty")
            doctor_name = row.get("doctor_name", "Unknown Doctor")
            availability = row.get("availability", "Availability not listed")

            response.append(
                f"🏥 {hospital_name} currently has {available_beds} beds. "
                f"Dr. {doctor_name} specializes in {specialty}. Availability: {availability}."
            )

    # Handle symptom-related results
    elif query_type == "symptom":
        for row in results[:3]:
            doctor_name = row.get("doctor_name", "Unknown Doctor")
            hospital_name = row.get("hospital_name", "Unknown Hospital")
            specialty = row.get("specialty", "Unknown Specialty")
            experience = row.get("experience_years", "N/A")
            availability = row.get("availability", "Availability not listed")

            response.append(
                f"For your symptom, Dr. {doctor_name} ({specialty}, {experience} years experience) "
                f"is available at {hospital_name}. Status: {availability}."
            )

    # Join results into a polite response
    return "\n\n".join(response)


# -------------------- Runtime --------------------
'''if __name__ == "__main__":
    print("🤖 Medical Assistant Ready! Ask me about hospitals, doctors, or symptoms.")
    while True:
        user_query = input("\n🩺 Your question (or type 'exit'): ")
        if user_query.lower() == "exit":
            break

        # Step 1: Normalize
        clean_query = normalize_input(user_query)

        # Step 2: Get SQL from LLaMA
        llama_output = ask_llama(clean_query)
        sql_query = extract_sql(llama_output)

        if not sql_query:
            print("⚠️ Sorry, I couldn't generate a valid query. LLaMA output:", llama_output)
            continue

        # Step 3: Execute SQL
        try:
            print("Executing SQL:", sql_query)
            cur.execute(sql_query)
            rows = cur.fetchall()
            print("Raw rows fetched:", rows)

            # Step 4: Format into natural response
            # Detect query type (simple keyword-based heuristic)
            lower_query = clean_query.lower()

            if any(word in lower_query for word in ["hospital", "hospitals", "beds"]):
                 query_type = "hospital"
            elif any(word in lower_query for word in ["fever", "pain", "headache", "symptom", "symptoms"]):
                 query_type = "symptom"
            else:
                 query_type = "doctor"

            response_text = format_results(rows, query_type=query_type)
            print("Formatting response for query type:", query_type)
            print("Formatting rows:", rows)


            print("\n💡", response_text)

        except Exception as e:
            print("❌ SQL execution error:", e)
llama_output = ask_llama(clean_query)
print("LLaMA output:", llama_output)
sql_query = extract_sql(llama_output)
print("Extracted SQL:", sql_query)
rows = cur.fetchall()
print("Rows fetched:", rows)'''
if __name__ == "__main__":
    print("🤖 Medical Assistant Ready! Ask me about hospitals, doctors, or symptoms.")
    while True:
        user_query = input("\n🩺 Your question (or type 'exit'): ")
        if user_query.lower() == "exit":
            break

        clean_query = normalize_input(user_query)

        try:
            llama_output = ask_llama(clean_query)
            print("LLaMA output:", llama_output)
            sql_query = extract_sql(llama_output)
            print("Extracted SQL:", sql_query)

            if not sql_query:
                print("⚠️ Sorry, I couldn't generate a valid query.")
                continue

            print("Executing SQL:", sql_query)
            cur.execute(sql_query)
            rows = cur.fetchall()
            print("Rows fetched:", rows)

            lower_query = clean_query.lower()
            if any(word in lower_query for word in ["hospital", "hospitals", "beds"]):
                query_type = "hospital"
            elif any(word in lower_query for word in ["fever", "pain", "headache", "symptom", "symptoms"]):
                query_type = "symptom"
            else:
                query_type = "doctor"

            response_text = format_results(rows, query_type=query_type)
            print("Formatting response for query type:", query_type)
            print("\n💡", response_text)

        except Exception as e:
            print("❌ SQL execution error:", e)


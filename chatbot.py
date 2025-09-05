import os
import psycopg2
import json
import re
from dotenv import load_dotenv
from groq import Groq
from thefuzz import process
import psycopg2.extras
import logging
import sqlparse  # For safer SQL parsing (install via pip install sqlparse)

# -------------------- Load Environment Variables --------------------
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# -------------------- Database Connection Helper --------------------
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

# -------------------- Prompt Template --------------------
SYSTEM_PROMPT = '''
You are a hospital-doctor information assistant.  
Your job is to convert user questions into SQL queries, execute them,  
and then return a polite natural-language answer.

You must strictly follow these rules:

1. Input: User will ask about hospitals, doctors, symptoms, specialties, beds, or availability.  
2. Output: You MUST return ONLY a valid SQL SELECT query (no explanations, no extra text).  
3. Always query using ONLY these tables:  
   - hospital_doctor_data(hospital_name, area, doctor_name, specialty, experience_years, availability, available_beds)  
   - symptom_specialty(symptom_keyword, specialty)  
4. Table and column names MUST NOT be altered, misspelled, or changed in any way. Use the names exactly as above.  
5. If the input is ambiguous or unclear, make the best guess to construct a logically valid SQL query.  
6. The query must ALWAYS limit the results to MAX 3 rows.  
7. If the user query implies available doctors or availability (keywords like "available", "free", "now", "open"),  
   always add "AND availability = TRUE" in the SQL WHERE clause.  
8. For text comparisons such as 'specialty' or 'symptom_keyword', use case-insensitive matching with ILIKE, e.g.:  
   SELECT ... FROM hospital_doctor_data WHERE specialty ILIKE '<specialty>' LIMIT 3;  
9. Do NOT include any column or table not specified above.  
10. You should ONLY focus on medical-related replies. Do NOT provide answers unrelated to medical, hospital, doctor, symptoms, or specialties.  
11. If a symptom from a user query is NOT found in the database, you MUST infer or fetch medically relevant information on your own to provide a helpful answer.  

--------------------  
DATABASE SCHEMA  
--------------------  
Table: hospital_doctor_data  
   - hospital_name TEXT  
   - area TEXT  
   - doctor_name TEXT  
   - specialty TEXT  
   - experience_years INT  
   - availability BOOLEAN  
   - available_beds INT  

Table: symptom_specialty  
   - symptom_keyword TEXT  
   - specialty TEXT  

--------------------  
TASK  
--------------------  
1. Carefully understand the user query and map it to the correct SQL SELECT statement using ONLY the above tables and columns.  
2. Return ONLY the SQL SELECT query, without any additional text or explanation.  
3. Use proper PostgreSQL syntax, respecting case insensitivity and the required availability filter.  
4. Ensure your SQL queries are syntactically correct and executable.  
5. When symptoms are missing in the database, do NOT return empty results—use your medical knowledge to infer or provide relevant information.  

-----------------------  
EXAMPLES  
-----------------------  

Example (Doctor query):  
SELECT doctor_name, specialty, experience_years, availability, hospital_name  
FROM hospital_doctor_data  
WHERE doctor_name = '<doctor_name>'  
LIMIT 3;  

Example (Hospital query):  
SELECT doctor_name, specialty, experience_years, availability, hospital_name  
FROM hospital_doctor_data  
WHERE hospital_name = '<hospital_name>'  
LIMIT 3;  

Example (Symptom query):  
SELECT doctor_name, specialty, experience_years, availability, hospital_name  
FROM hospital_doctor_data  
WHERE specialty IN (SELECT specialty FROM symptom_specialty WHERE symptom_keyword = '<symptom>')  
LIMIT 3;  
'''

def normalize_input(user_query: str) -> str:
    """Clean up messy user input for better matching"""
    text = user_query.lower()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace("’", "'").replace("''", "'")
    return text.strip()

def fetch_distinct_column_values(column_name: str, conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT DISTINCT {column_name} FROM hospital_doctor_data")
        values = [row[column_name] for row in cur.fetchall() if row[column_name]]
    return values

def fuzzy_match(user_input, column_values):
    """Fuzzy match user input to closest column value"""
    best_match = process.extractOne(user_input, column_values)
    return best_match[0] if best_match else user_input

def fuzzy_match_input(user_input: str, column_name: str, conn) -> str:
    distinct_values = fetch_distinct_column_values(column_name, conn)
    # Tokenize user input for safer replacement
    tokens = user_input.split()
    corrected_tokens = []
    for token in tokens:
        match = fuzzy_match(token, distinct_values)
        corrected_tokens.append(match if match else token)
    return ' '.join(corrected_tokens)

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
    return response.choices[0].message.content.strip()

def is_valid_select_query(sql_query: str) -> bool:
    """Basic validation to ensure query is a SELECT and no dangerous keywords"""
    parsed = sqlparse.parse(sql_query)
    if not parsed:
        return False
    stmt = parsed[0]
    # Check first token is SELECT
    if stmt.get_type() != 'SELECT':
        return False
    # Check for dangerous keywords
    forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE']
    sql_upper = sql_query.upper()
    if any(word in sql_upper for word in forbidden):
        return False
    return True

def add_availability_filter(sql_query: str) -> str:
    """
    Add 'availability = TRUE' filter safely to the WHERE clause.
    Uses sqlparse to parse and modify the query.
    """
    parsed = sqlparse.parse(sql_query)
    if not parsed:
        return sql_query  # fallback

    stmt = parsed[0]
    tokens = list(stmt.tokens)

    # Find WHERE clause token index
    where_idx = None
    for i, token in enumerate(tokens):
        if token.ttype is None and token.is_group and token.tokens:
            # Recursively check inside groups
            for subtoken in token.tokens:
                if subtoken.ttype is sqlparse.tokens.Keyword and subtoken.value.upper() == 'WHERE':
                    where_idx = i
                    break
        elif token.ttype is sqlparse.tokens.Keyword and token.value.upper() == 'WHERE':
            where_idx = i
            break

    if where_idx is not None:
        # Insert 'availability = TRUE AND' after WHERE
        # This is a simplified approach: just replace WHERE with WHERE availability = TRUE AND
        # Rebuild query string
        sql_query = re.sub(r'(?i)\bWHERE\b', 'WHERE availability = TRUE AND', sql_query, count=1)
    else:
        # No WHERE clause, add one before LIMIT
        sql_query = re.sub(r'(?i)\bLIMIT\b', 'WHERE availability = TRUE LIMIT', sql_query, count=1)

    return sql_query

def format_results(results, query_type="doctor"):
    """
    Format SQL query results into a polite natural language response.
    Includes doctor availability.
    """
    if not results or len(results) == 0:
        return "❌ I could not find an exact match. Please try with another hospital, doctor, or symptom."

    response = []

    if query_type == "doctor":
        for row in results[:3]:  # Limit to top 3
            doctor_name = row.get("doctor_name", "Unknown Doctor")
            # Case-insensitive check for "Dr."
            if re.match(r"(?i)^dr\.", doctor_name):
                doctor_name_display = doctor_name
            else:
                doctor_name_display = f"Dr. {doctor_name}"
            hospital_name = row.get("hospital_name", "Unknown Hospital")
            specialty = row.get("specialty", "Unknown Specialty")
            experience = row.get("experience_years", "N/A")
            availability = row.get("availability", "Availability not listed")

            response.append(
                f"🩺 {doctor_name_display} ({specialty}, {experience} years experience) "
                f"is available at {hospital_name}. Current status: {availability}."
            )

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

    elif query_type == "symptom":
        for row in results[:3]:
            doctor_name = row.get("doctor_name", "Unknown Doctor")
            if re.match(r"(?i)^dr\.", doctor_name):
                doctor_name_display = doctor_name
            else:
                doctor_name_display = f"Dr. {doctor_name}"
            hospital_name = row.get("hospital_name", "Unknown Hospital")
            specialty = row.get("specialty", "Unknown Specialty")
            experience = row.get("experience_years", "N/A")
            availability = row.get("availability", "Availability not listed")

            response.append(
                f"For your symptom, {doctor_name_display} ({specialty}, {experience} years experience) "
                f"is available at {hospital_name}. Status: {availability}."
            )

    return "\n\n".join(response)

def get_chatbot_reply(user_query):
    clean_query = normalize_input(user_query)

    # Open DB connection here and close after use
    with get_db_connection() as conn:
        # Use fuzzy matching to correct typos on hospital names and specialties before querying Groq
        clean_query = fuzzy_match_input(clean_query, "hospital_name", conn)
        clean_query = fuzzy_match_input(clean_query, "specialty", conn)

        availability_filter = any(word in clean_query for word in ["available", "availability", "currently available", "free", "open", "now"])

        llama_output = ask_llama(clean_query)
        sql_query = llama_output.strip()

        # Make specialty and symptom_keyword filters case-insensitive
        sql_query = re.sub(r"specialty\s*=\s*'([^']*)'", r"specialty ILIKE '\1'", sql_query, flags=re.I)
        sql_query = re.sub(r"symptom_keyword\s*=\s*'([^']*)'", r"symptom_keyword ILIKE '\1'", sql_query, flags=re.I)

        # Add availability filter if applicable
        if availability_filter and "availability" not in sql_query.lower():
            sql_query = add_availability_filter(sql_query)

        # Validate SQL query before execution
        if not is_valid_select_query(sql_query):
            return "⚠️ Sorry, generated output is not a valid SELECT SQL query."

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql_query)
            rows = cur.fetchall()

        # Detect query type from SQL query instead of hardcoded keywords
        sql_lower = sql_query.lower()
        if "hospital_name" in sql_lower or "available_beds" in sql_lower:
            query_type = "hospital"
        elif "symptom_keyword" in sql_lower or "symptom_specialty" in sql_lower:
            query_type = "symptom"
        else:
            query_type = "doctor"

        response_text = format_results(rows, query_type=query_type)
        return response_text

if __name__ == "__main__":
    print("🤖 Medical Assistant Ready! Ask me about hospitals, doctors, or symptoms.")
    while True:
        user_query = input("\n🩺 Your question (or type 'exit'): ")
        if user_query.lower() == "exit":
            break

        try:
            response = get_chatbot_reply(user_query)
            print("\n💡 Chatbot response:\n", response)
        except Exception as e:
            logger.error("Error in chatbot reply: %s", e)
            print("❌ Error:", e)

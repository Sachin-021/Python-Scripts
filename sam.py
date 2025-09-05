'''import os
import csv
import re
import json
from dotenv import load_dotenv
from groq import Groq
from thefuzz import process

# -------------------- Load environment and initialize Groq client --------------------
load_dotenv()
client = Groq(api_key=os.getenv("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"))

# -------------------- Specialty Map --------------------
specialty_map = {
    "chest pain": "Cardiology",
    "heart problem": "Cardiology",
    "cardiology": "Cardiology",
    "fracture": "Orthopedics",
    "bone pain": "Orthopedics",
    "orthopedics": "Orthopedics",
    "eye problem": "Ophthalmology",
    "vision issue": "Ophthalmology",
    "ophthalmology": "Ophthalmology",
    "stomach pain": "Gastroenterology",
    "gastro": "Gastroenterology",
    "gastroenterology": "Gastroenterology",
    "skin rash": "Dermatology",
    "dermatology": "Dermatology",
    "pregnancy": "Gynecology",
    "gynecology": "Gynecology",
    "fever": "General Medicine",
    "general medicine": "General Medicine",
    "nervous problem": "Neurology",
    "neurology": "Neurology",
    "headache": "Neurology",
    "seizure": "Neurology",
    "memory loss": "Neurology",
    "oncology": "Oncology",
    "cancer": "Oncology",
    "tumor": "Oncology",
    "chemotherapy": "Oncology",
    "radiation": "Oncology"
}

# -------------------- Hospital list --------------------
hospital_list = [
    "Coimbatore Medical Center", "Kovai Medical College Hospital", "KG Hospital",
    "PSG Hospitals", "Sri Ramakrishna Hospital", "Ganga Hospital", "Gem Hospital",
    "Aravind Eye Hospital", "Sugam Hospital", "Vijaya Hospital", "Medwin Specialty Hospital",
    "Green Leaf Hospital", "Lotus Heart Center", "Sundaram Multispecialty",
    "Royal Care Super Specialty", "Trustwell Hospital", "New Life Hospital",
    "Wellbeing Hospital", "Hope Medical Center", "Bright Health Hospital"
]

# Optional: Location map if you want to associate hospitals with areas
location_map = {
    "Coimbatore": ["Coimbatore Medical Center", "Kovai Medical College Hospital", "PSG Hospitals", "Sri Ramakrishna Hospital"],
    "Erode": ["KG Hospital", "Sugam Hospital", "Gem Hospital"],
    "Madurai": ["Vijaya Hospital", "Aravind Eye Hospital"],
    # add more locations as needed
}

# -------------------- Utility functions --------------------
def normalize(text):
    if not text:
        return ""
    ignore_words = ["hospital", "center", "clinic", "medical", "super specialty"]
    text = text.lower()
    for w in ignore_words:
        text = text.replace(w, "")
    text = re.sub(r'\s+', '', text)
    return text

def fuzzy_extract_best(query, choices, cutoff=70):
    if not query or not choices:
        return None
    match, score = process.extractOne(query, choices)
    if score >= cutoff:
        return match
    return None

def extract_json(text):
    try:
        matches = re.findall(r"\{.*?\}", text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except:
                continue
    except:
        return {}
    return {}

# -------------------- LLaMA entity extraction --------------------
examples = """
:User    I have memory loss issues, can I get a doctor at Coimbatore Medical Center?
Assistant: {"problem": "memory loss", "doctor": null, "hospital": "Coimbatore Medical Center", "location": null}

:User    I have a skin rash, is there a Dermatology doctor at PSG Hospitals?
Assistant: {"problem": "skin rash", "doctor": null, "hospital": "PSG Hospitals", "location": null}

:User    Is Dr. Arjun available at Ganga Hospital for Orthopedics?
Assistant: {"problem": null, "doctor": "Dr. Arjun", "hospital": "Ganga Hospital", "location": null}

:User    I have cancer what hospital or doctor should I visit?
Assistant: {"problem": "cancer", "doctor": null, "hospital": null, "location": null}
"""

def extract_entities(user_query):
    prompt = f"""
You are a medical chatbot. Extract structured entities from the user query.

Return ONLY JSON with keys: problem, doctor, hospital, location.

Rules:
- Return valid JSON only.
- If you don't know a value, use null.
- Do not explain or add alternatives in the JSON.
- Do not invent doctor names.

Examples:
{examples}

Now extract entities from:
"{user_query}"
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        return extract_json(content)
    except:
        return None

# -------------------- Symptom and hospital extraction --------------------
def extract_symptom_and_hospital(problem, hospital):
    symptom = fuzzy_extract_best(problem.lower(), list(specialty_map.keys())) if problem else None
    true_hospital = None
    if hospital:
        hospital_norm = normalize(hospital)
        hospital_norm_list = [normalize(h) for h in hospital_list]
        hospital_match_norm = fuzzy_extract_best(hospital_norm, hospital_norm_list)
        if hospital_match_norm:
            for h in hospital_list:
                if normalize(h) == hospital_match_norm:
                    true_hospital = h
                    break
    return symptom, true_hospital

# -------------------- Find doctors from CSV --------------------
def find_doctors(filepath, specialty, hospital, max_alts=2):
    doctors_primary, doctors_alt = [], []
    seen_hospitals = set()
    hospital_norm = normalize(hospital) if hospital else None
    specialty_norm = specialty.lower() if specialty else None
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('availability', '').strip().lower() != "true":
                continue
            row_hospital_norm = normalize(row.get('hospital_name', ''))
            row_specialty_norm = row.get('specialty', '').lower()
            if hospital_norm and row_hospital_norm == hospital_norm and row_specialty_norm == specialty_norm:
                doctors_primary.append(row)
            elif row_specialty_norm == specialty_norm:
                key = (row.get('hospital_name', ''), row.get('area', ''))
                if key not in seen_hospitals and (not hospital_norm or row_hospital_norm != hospital_norm):
                    doctors_alt.append(row)
                    seen_hospitals.add(key)
                    if len(doctors_alt) == max_alts:
                        break
    return doctors_primary, doctors_alt

def format_doc(row):
    return (f"Doctor: {row.get('doctor_name', 'N/A')} | Specialty: {row.get('specialty', 'N/A')} | "
            f"Experience: {row.get('experience_years', 'N/A')} yrs | Hospital: {row.get('hospital_name', 'N/A')} ({row.get('area', 'N/A')}) | Beds: {row.get('available_beds', 'N/A')}")

# -------------------- Main chatbot reply --------------------
def get_chatbot_reply(user_text, filepath="database_hosp_extended.csv"):
    entities = extract_entities(user_text)
    if not entities:
        return "Sorry, I couldn't understand your query. Please try rephrasing."

    problem, doctor, hospital, location = entities.get("problem"), entities.get("doctor"), entities.get("hospital"), entities.get("location")
    symptom, true_hospital = extract_symptom_and_hospital(problem, hospital)
    if not symptom:
        return "Sorry, I couldn't identify your health issue. Please rephrase or specify your symptom clearly."
    specialty = specialty_map.get(symptom)
    doctors_primary, doctors_alt = find_doctors(filepath, specialty, true_hospital)
    hospital_display = true_hospital if true_hospital else "Not specified"

    if doctors_primary:
        doc = doctors_primary[0]
        short_reply = f"{specialty} → {doc.get('doctor_name')} ({doc.get('experience_years')} yrs, {doc.get('area')}, {doc.get('hospital_name')})"
    elif doctors_alt:
        doc = doctors_alt[0]
        short_reply = f"No. Alternatives → {doc.get('doctor_name')} ({doc.get('specialty')}, {doc.get('hospital_name')})"
    else:
        short_reply = "No doctors found for your query."

    detailed_lines = []
    if doctors_primary:
        detailed_lines.append("Doctor(s) available at requested hospital:")
        for doc in doctors_primary:
            detailed_lines.append(format_doc(doc))
    elif doctors_alt:
        detailed_lines.append("Alternative hospitals with available doctors for the same specialty:")
        for doc in doctors_alt:
            detailed_lines.append(format_doc(doc))

    reply = short_reply
    if detailed_lines:
        reply += "\n\n" + "\n".join(detailed_lines)

    return reply

# -------------------- Run chatbot --------------------
if __name__ == "__main__":
    print("Welcome to the Medical Chatbot! Type 'exit' or 'quit' to stop.")
    while True:
        user_input = input("Ask your health question: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        response = get_chatbot_reply(user_input, filepath="database_hosp_extended.csv")
        print(response)'''

import os
import csv
import re
from dotenv import load_dotenv
from groq import Groq
from thefuzz import process

# Load environment and initialize Groq client
load_dotenv()
client = Groq(api_key=os.getenv("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"))

# Symptom to Specialty Map (expand with synonyms etc.)
specialty_map = {
    "chest pain": "Cardiology",
    "heart problem": "Cardiology",
    "cardiology": "Cardiology",

    "fracture": "Orthopedics",
    "bone pain": "Orthopedics",
    "orthopedics": "Orthopedics",

    "eye problem": "Ophthalmology",
    "vision issue": "Ophthalmology",
    "ophthalmology": "Ophthalmology",

    "stomach pain": "Gastroenterology",
    "gastro": "Gastroenterology",
    "gastroenterology": "Gastroenterology",

    "skin rash": "Dermatology",
    "dermatology": "Dermatology",

    "pregnancy": "Gynecology",
    "gynecology": "Gynecology",

    "fever": "General Medicine",
    "general medicine": "General Medicine",

    "nervous problem": "Neurology",
    "neurology": "Neurology",
    "headache": "Neurology",
    "seizure": "Neurology",
    "memory loss": "Neurology",

    # ✅ Add this block for Oncology
    "oncology": "Oncology",
    "cancer": "Oncology",
    "tumor": "Oncology",
    "chemotherapy": "Oncology",
    "radiation": "Oncology"
}


# Hospital list from CSV -- make sure it's complete and normalized
hospital_list = [
    "Coimbatore Medical Center",
    "Kovai Medical College Hospital",
    "KG Hospital",
    "PSG Hospitals",
    "Sri Ramakrishna Hospital",
    "Ganga Hospital",
    "Gem Hospital", 
    "Aravind Eye Hospital",
    "Sugam Hospital",
    "Vijaya Hospital",
    "Medwin Specialty Hospital",
    "Green Leaf Hospital",
    "Lotus Heart Center",
    "Sundaram Multispecialty",
    "Royal Care Super Specialty",
    "Trustwell Hospital",
    "New Life Hospital",
    "Wellbeing Hospital",
    "Hope Medical Center",
    "Bright Health Hospital"
]

def normalize(text):
    """Normalize strings for robust comparison."""
    ignore_words = ["hospital", "center", "clinic", "medical", "super specialty"]
    text = text.lower()
    for w in ignore_words:
        text = text.replace(w, "")
    return re.sub(r'\s+', '', text)

def fuzzy_extract_best(query, choices, cutoff=70):
    """Return best fuzzy match above cutoff or None."""
    match, score = process.extractOne(query, choices)
    if score >= cutoff:
        return match
    return None

def extract_symptom_and_hospital(user_text):
    user_text_norm = user_text.lower()
    # Extract symptom using fuzzy matching
    symptom = fuzzy_extract_best(user_text_norm, list(specialty_map.keys()))
    # Extract hospital using fuzzy matching on normalized names
    hospital_norm_list = [h.lower() for h in hospital_list]
    hospital_match = fuzzy_extract_best(user_text_norm, hospital_norm_list)
    true_hospital = None
    if hospital_match:
        # Find original casing hospital name
        for h in hospital_list:
            if h.lower() == hospital_match:
                true_hospital = h
                break
    return symptom, true_hospital

def find_doctors(filepath, specialty, hospital, max_alts=2):
    doctors_primary = []
    doctors_alt = []
    seen_hospitals = set()
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['availability'].strip().lower() != "true":
                continue
            # Normalize for matching 
            row_hospital_norm = normalize(row['hospital_name'])
            hospital_norm = normalize(hospital) if hospital else None
            row_specialty_norm = row['specialty'].lower()
            specialty_norm = specialty.lower()

            # Primary hospital and specialty match
            if hospital_norm and row_hospital_norm == hospital_norm and row_specialty_norm == specialty_norm:
                doctors_primary.append(row)
            # Alternatives: same specialty, different hospital
            elif row_specialty_norm == specialty_norm:
                key = (row['hospital_name'], row['area'])
                if key not in seen_hospitals and (not hospital_norm or row_hospital_norm != hospital_norm):
                    doctors_alt.append(row)
                    seen_hospitals.add(key)
                    if len(doctors_alt) == max_alts:
                        break
    return doctors_primary, doctors_alt

def format_doc(row):
    return (f"Doctor: {row['doctor_name']} | Specialty: {row['specialty']} | "
            f"Experience: {row['experience_years']} yrs | Hospital: {row['hospital_name']} ({row['area']}) | Beds: {row['available_beds']}")

def get_chatbot_reply(user_text, filepath="database_hosp.csv"):
    symptom, hospital = extract_symptom_and_hospital(user_text)
    if not symptom:
        return "Sorry, I couldn't identify your health issue. Please rephrase or specify your symptom clearly."
    specialty = specialty_map.get(symptom, None)
    if not specialty:
        return "Sorry, I couldn't match your symptom to a medical specialty. Please rephrase."
    doctors_primary, doctors_alt = find_doctors(filepath, specialty, hospital)
    hospital_display = hospital if hospital else "Not specified"
    strict_prompt = f"""
You are a helpful medical chatbot. ONLY use the data provided; do NOT invent or embellish details.

User request: "{user_text}"
Symptom: {symptom}
Hospital: {hospital_display}

Doctor(s) at requested hospital:
{format_doc(doctors_primary[0]) if doctors_primary else "None available."}

Alternative hospitals for the same specialty (up to 2):
{chr(10).join([format_doc(doc) for doc in doctors_alt]) if doctors_alt else "None available."}

Instructions:
- Clearly recommend available doctors from the requested hospital (if any).
- If none are found, politely explain so and offer up to 2 alternative hospital/doctor specialists.
- Be friendly, clear, and actionable.
- Never add extra information not present above.
    """
    reply = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": strict_prompt}],
        temperature=0.2
    )
    return reply.choices[0].message.content

# --------- DEPLOYMENT STARTS HERE ---------
if __name__ == "__main__":
    user_input = input("Ask your health question: ")
    print(get_chatbot_reply(user_input, filepath="C:\\Users\\Sachi\\Downloads\\database_hosp.csv"))
#chatbot.py






'''import os
import csv
import re
import json
from dotenv import load_dotenv
from groq import Groq
from thefuzz import process

# -------------------- Load environment and initialize Groq client --------------------
load_dotenv()
client = Groq(api_key=os.getenv("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"))

# -------------------- Specialty Map --------------------
specialty_map = {
    "chest pain": "Cardiology",
    "heart problem": "Cardiology",
    "cardiology": "Cardiology",
    "fracture": "Orthopedics",
    "bone pain": "Orthopedics",
    "orthopedics": "Orthopedics",
    "eye problem": "Ophthalmology",
    "vision issue": "Ophthalmology",
    "ophthalmology": "Ophthalmology",
    "stomach pain": "Gastroenterology",
    "gastro": "Gastroenterology",
    "gastroenterology": "Gastroenterology",
    "skin rash": "Dermatology",
    "dermatology": "Dermatology",
    "pregnancy": "Gynecology",
    "gynecology": "Gynecology",
    "fever": "General Medicine",
    "general medicine": "General Medicine",
    "nervous problem": "Neurology",
    "neurology": "Neurology",
    "headache": "Neurology",
    "seizure": "Neurology",
    "memory loss": "Neurology",
    "oncology": "Oncology",
    "cancer": "Oncology",
    "tumor": "Oncology",
    "chemotherapy": "Oncology",
    "radiation": "Oncology"
}

# -------------------- Hospital list --------------------
hospital_list = [
    "Coimbatore Medical Center", "Kovai Medical College Hospital", "KG Hospital",
    "PSG Hospitals", "Sri Ramakrishna Hospital", "Ganga Hospital", "Gem Hospital",
    "Aravind Eye Hospital", "Sugam Hospital", "Vijaya Hospital", "Medwin Specialty Hospital",
    "Green Leaf Hospital", "Lotus Heart Center", "Sundaram Multispecialty",
    "Royal Care Super Specialty", "Trustwell Hospital", "New Life Hospital",
    "Wellbeing Hospital", "Hope Medical Center", "Bright Health Hospital",
    "Apollo Specialty Hospital", "Fortis Health Center", "Sri Krishna Medical College",
    "LifeLine Multispecialty", "Global Health City", "Velan Eye Hospital",
    "Shanthi Children’s Hospital", "Bharathi Ortho Center", "Aruna Women’s Clinic",
    "Coimbatore Neuro Care", "Sri Venkateswara Institute of Medical Sciences",
    "Nirmala General Hospital", "Metro Heart Institute", "Santhosh Medical College",
    "Lotus Women’s Hospital", "Kovai Heart Institute", "Green Valley Health Center",
    "Hope Specialty Hospital", "Trinity Care Hospital", "Elite Health Care",
    "Rainbow Children’s Hospital", "MediLife Multispecialty", "Vision Plus Eye Hospital",
    "Shree Balaji Medical Institute", "WellCare Hospital", "Sunshine Neuro Center",
    "Grace Medical College", "Prime Care Hospital", "Janani Women & Child Hospital",
    "Sundar Eye Institute", "Harmony Health Center", "Nova Medical College",
    "Sri Meenakshi Health Center", "Aster Specialty Hospital", "Sankara Neuro Institute",
    "Royal Heart Care", "LifeSpring Hospital", "Heritage Multispecialty",
    "Unity Medical Institute", "Sri Sai Health Center", "Healing Touch Hospital",
    "Sacred Heart Medical College", "Bluebell Hospital", "Skyline Health Institute",
    "Athena Women’s Hospital", "Wellbeing Care Hospital", "MediTrust Hospital",
    "Sri Ramana Neuro Hospital", "Galaxy Specialty Clinic", "Om Shakthi Medical Center",
    "Starline Children’s Hospital", "Brahma Ortho Institute", "Zenith Health College",
    "Veda Women’s Hospital", "Sapphire Eye Hospital", "Amrita Specialty Hospital",
    "Phoenix Heart Institute", "Arcadia Health Center", "MedStar Multispecialty",
    "Vital Care Hospital", "Cosmos Medical Institute", "Emerald Eye Clinic",
    "Sterling Neuro Care", "Cura Medical College"
]

# Optional: Location map if you want to associate hospitals with areas
location_map = {
    "Coimbatore": ["Coimbatore Medical Center", "Kovai Medical College Hospital", "PSG Hospitals", "Sri Ramakrishna Hospital"],
    "Erode": ["KG Hospital", "Sugam Hospital", "Gem Hospital"],
    "Madurai": ["Vijaya Hospital", "Aravind Eye Hospital"],
    # add more locations as needed
}

# -------------------- Utility functions --------------------
def normalize(text):
    if not text:
        return ""
    ignore_words = ["hospital", "center", "clinic", "medical", "super specialty"]
    text = text.lower()
    for w in ignore_words:
        text = text.replace(w, "")
    text = re.sub(r'\s+', '', text)
    return text

def fuzzy_extract_best(query, choices, cutoff=70):
    if not query or not choices:
        return None
    match, score = process.extractOne(query, choices)
    if score >= cutoff:
        return match
    return None

def extract_json(text):
    try:
        matches = re.findall(r"\{.*?\}", text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except:
                continue
    except:
        return {}
    return {}

# -------------------- LLaMA entity extraction --------------------
examples = """
:User    I have memory loss issues, can I get a doctor at Coimbatore Medical Center?
Assistant: {"problem": "memory loss", "doctor": null, "hospital": "Coimbatore Medical Center", "location": null}

:User    I have a skin rash, is there a Dermatology doctor at PSG Hospitals?
Assistant: {"problem": "skin rash", "doctor": null, "hospital": "PSG Hospitals", "location": null}

:User    Is Dr. Arjun available at Ganga Hospital for Orthopedics?
Assistant: {"problem": null, "doctor": "Dr. Arjun", "hospital": "Ganga Hospital", "location": null}

:User    I have cancer what hospital or doctor should I visit?
Assistant: {"problem": "cancer", "doctor": null, "hospital": null, "location": null}
"""

def extract_entities(user_query):
    prompt = f"""
You are a medical chatbot. Extract structured entities from the user query.

Return ONLY JSON with keys: problem, doctor, hospital, location.

Rules:
- Return valid JSON only.
- If you don't know a value, use null.
- Do not explain or add alternatives in the JSON.
- Do not invent doctor names.
- If the doctor is asked dont give random values,analyse and say
- If hospital is asked do the same as for doctor
- Do not share any sensitive reply and be strict towards clarity 
- If doctors,hospitals are asked provide it for the query given

Examples:
{examples}

Now extract entities from:
"{user_query}"
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        return extract_json(content)
    except:
        return None

# -------------------- Symptom and hospital extraction --------------------
def extract_symptom_and_hospital(problem, hospital):
    symptom = fuzzy_extract_best(problem.lower(), list(specialty_map.keys())) if problem else None
    true_hospital = None
    if hospital:
        hospital_norm = normalize(hospital)
        hospital_norm_list = [normalize(h) for h in hospital_list]
        hospital_match_norm = fuzzy_extract_best(hospital_norm, hospital_norm_list)
        if hospital_match_norm:
            for h in hospital_list:
                if normalize(h) == hospital_match_norm:
                    true_hospital = h
                    break
    return symptom, true_hospital

# -------------------- Find doctors from CSV --------------------
def find_doctors(filepath, specialty, hospital, max_alts=2):
    doctors_primary, doctors_alt = [], []
    seen_hospitals = set()
    hospital_norm = normalize(hospital) if hospital else None
    specialty_norm = specialty.lower() if specialty else None
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('availability', '').strip().lower() != "true":
                continue
            row_hospital_norm = normalize(row.get('hospital_name', ''))
            row_specialty_norm = row.get('specialty', '').lower()
            if hospital_norm and row_hospital_norm == hospital_norm and row_specialty_norm == specialty_norm:
                doctors_primary.append(row)
            elif row_specialty_norm == specialty_norm:
                key = (row.get('hospital_name', ''), row.get('area', ''))
                if key not in seen_hospitals and (not hospital_norm or row_hospital_norm != hospital_norm):
                    doctors_alt.append(row)
                    seen_hospitals.add(key)
                    if len(doctors_alt) == max_alts:
                        break
    return doctors_primary, doctors_alt

def format_doc(row):
    return (f"Doctor: {row.get('doctor_name', 'N/A')} | Specialty: {row.get('specialty', 'N/A')} | "
            f"Experience: {row.get('experience_years', 'N/A')} yrs | Hospital: {row.get('hospital_name', 'N/A')} ({row.get('area', 'N/A')}) | Beds: {row.get('available_beds', 'N/A')}")

# -------------------- Main chatbot reply --------------------
def get_chatbot_reply(user_text, filepath="database_hosp_extended.csv"):
    entities = extract_entities(user_text)
    if not entities:
        return "Sorry, I couldn't understand your query. Please try rephrasing."

    problem, doctor, hospital, location = entities.get("problem"), entities.get("doctor"), entities.get("hospital"), entities.get("location")
    symptom, true_hospital = extract_symptom_and_hospital(problem, hospital)
    if not symptom:
        return "Sorry, I couldn't identify your health issue. Please rephrase or specify your symptom clearly."
    specialty = specialty_map.get(symptom)
    doctors_primary, doctors_alt = find_doctors(filepath, specialty, true_hospital)
    hospital_display = true_hospital if true_hospital else "Not specified"

    if doctors_primary:
        doc = doctors_primary[0]
        short_reply = f"{specialty} → {doc.get('doctor_name')} ({doc.get('experience_years')} yrs, {doc.get('area')}, {doc.get('hospital_name')})"
    elif doctors_alt:
        doc = doctors_alt[0]
        short_reply = f"No. Alternatives → {doc.get('doctor_name')} ({doc.get('specialty')}, {doc.get('hospital_name')})"
    else:
        short_reply = "No doctors found for your query."

    detailed_lines = []
    if doctors_primary:
        detailed_lines.append("Doctor(s) available at requested hospital:")
        for doc in doctors_primary:
            detailed_lines.append(format_doc(doc))
    elif doctors_alt:
        detailed_lines.append("Alternative hospitals with available doctors for the same specialty:")
        for doc in doctors_alt:
            detailed_lines.append(format_doc(doc))

    reply = short_reply
    if detailed_lines:
        reply += "\n\n" + "\n".join(detailed_lines)

    return reply

# -------------------- Run chatbot --------------------
if __name__ == "__main__":
    print("Welcome to the Medical Chatbot! Type 'exit' or 'quit' to stop.")
    while True:
        user_input = input("Ask your health question: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        response = get_chatbot_reply(user_input, filepath="database_hosp_extended.csv")
        print(response)'''













SYSTEM_PROMPT = """
You are a hospital-doctor information assistant.  
Your job is to convert user questions into SQL queries, execute them, 
and then return a polite natural-language answer.

You must follow these rules strictly:

1. Input: User will ask about hospitals, doctors, symptoms, specialties, beds, or availability.
2. Output: You MUST return ONLY a valid SQL query (no explanations, no natural text).
3. Always query using ONLY these tables:
   - hospital_doctor_data(hospital_name, area, doctor_name, specialty, experience_years, availability, available_beds)
   - symptom_specialty(symptom_keyword, specialty)
4. DO NOT make any typo or change in table or column names. Use the table names exactly:
   hospital_doctor_data, symptom_specialty
5. If input is unclear, make the best SQL guess.
6. Always limit results to MAX 3 rows.
7. If the user query implies available doctors (words like "available", "free", "now"), always add "AND availability = TRUE" in your SQL WHERE clause.
8. When filtering text columns such as 'specialty', perform case-insensitive comparisons using ILIKE in PostgreSQL, (e.g.):
SELECT ... FROM hospital_doctor_data WHERE specialty ILIKE '<specialty>' LIMIT 3;

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

--------------------
TASK
--------------------
1. Understand user query and map it to SQL using ONLY the above tables.  
2. Output ONLY the SQL query.  
3. Use SELECT statements fetching relevant columns.  
4. Examples:

Example (Doctor query):  
SELECT doctor_name, specialty, experience_years, availability, hospital_name FROM hospital_doctor_data WHERE doctor_name = '<doctor_name>' LIMIT 3;

Example (Hospital query):  
SELECT doctor_name, specialty, experience_years, availability, hospital_name FROM hospital_doctor_data WHERE hospital_name = '<hospital_name>' LIMIT 3;

Example (Symptom query):  
SELECT doctor_name, specialty, experience_years, availability, hospital_name FROM hospital_doctor_data WHERE specialty IN (SELECT specialty FROM symptom_specialty WHERE symptom_keyword = '<symptom>') LIMIT 3;
"""

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
   - availability TEXT  
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

def fetch_distinct_column_values(column_name: str):
    cur.execute(f"SELECT DISTINCT {column_name} FROM hospital_doctor_data")
    values = [row[column_name] for row in cur.fetchall() if row[column_name]]
    return values

def fuzzy_match(user_input, column_values):
    """Fuzzy match user input to closest column value"""
    best_match = process.extractOne(user_input, column_values)
    return best_match[0] if best_match else user_input

def fuzzy_match_input(user_input: str, column_name: str) -> str:
    distinct_values = fetch_distinct_column_values(column_name)
    for val in distinct_values:
        if val and val.lower() in user_input:
            corrected = fuzzy_match(val, distinct_values)
            user_input = user_input.replace(val.lower(), corrected.lower())
    return user_input

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
            # Avoid double "Dr." prefix
            if doctor_name.lower().startswith("dr."):
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
            if doctor_name.lower().startswith("dr."):
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

def get_chatbot_reply(user_query, filepath):
    clean_query = normalize_input(user_query)

    # Use fuzzy matching to correct typos on hospital names and specialties before querying Groq
    clean_query = fuzzy_match_input(clean_query, "hospital_name")
    clean_query = fuzzy_match_input(clean_query, "specialty")

    availability_filter = any(word in clean_query for word in ["available", "availability", "currently available", "free", "open", "now"])

    llama_output = ask_llama(clean_query)
    sql_query = llama_output.strip()

    # Make specialty and symptom_keyword filters case-insensitive
    sql_query = re.sub(r"specialty\s*=\s*'([^']*)'", r"specialty ILIKE '\1'", sql_query, flags=re.I)
    sql_query = re.sub(r"symptom_keyword\s*=\s*'([^']*)'", r"symptom_keyword ILIKE '\1'", sql_query, flags=re.I)

    # Add availability filter if applicable
    if availability_filter and "availability" not in sql_query.lower():
        if "where" in sql_query.lower():
            sql_query = re.sub(r"where", "WHERE availability = TRUE AND ", sql_query, flags=re.I, count=1)
        else:
            sql_query = re.sub(r"limit", "WHERE availability = TRUE LIMIT", sql_query, flags=re.I, count=1)

    if not sql_query.lower().startswith("select"):
        return "⚠️ Sorry, generated output is not a valid SELECT SQL query."

    cur.execute(sql_query)
    rows = cur.fetchall()

    # Detect query type from user input
    if any(word in clean_query for word in ["hospital", "hospitals", "beds"]):
        query_type = "hospital"
    elif any(word in clean_query for word in ["fever", "pain", "headache", "symptom", "symptoms"]):
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
            response = get_chatbot_reply(user_query, filepath="database_hosp_extended.csv")
            print("\n💡 Chatbot response:\n", response)
        except Exception as e:
            print("❌ Error:", e)

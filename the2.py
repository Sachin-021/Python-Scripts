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

# -------------------- Utility functions --------------------
def normalize(text):
    if not text:
        return ""
    ignore_words = ["hospital", "center", "clinic", "medical", "super specialty"]
    text = text.lower()
    for w in ignore_words:
        text = text.replace(w, "")
    text = re.sub(r'\s+', '', text)  # remove all spaces
    return text


def fuzzy_extract_best(query, choices, cutoff=70):
    """Return best fuzzy match above cutoff or None."""
    if not query or not choices:
        return None
    match, score = process.extractOne(query, choices)
    if score >= cutoff:
        return match
    return None

def extract_json(text):
    """Extract first valid JSON object from text."""
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

# -------------------- Entity extraction with LLaMA --------------------
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
        data = extract_json(content)
        if not data:
            return None
        return data
    except Exception as e:
        return None

# -------------------- Extract symptom and hospital with fuzzy matching --------------------
def extract_symptom_and_hospital(problem, hospital):
    symptom = None
    if problem:
        symptom = fuzzy_extract_best(problem.lower(), list(specialty_map.keys()))
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
    doctors_primary = []
    doctors_alt = []
    seen_hospitals = set()
    hospital_norm = normalize(hospital) if hospital else None
    specialty_norm = specialty.lower() if specialty else None
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            availability = row.get('availability', '').strip().lower()
            if availability != "true":
                continue
            row_hospital_norm = normalize(row.get('hospital_name', ''))
            row_specialty_norm = row.get('specialty', '').lower()

            # Uncomment below to debug matching
            # print(f"Checking doctor {row.get('doctor_name')} at {row.get('hospital_name')} (norm: {row_hospital_norm}), specialty: {row_specialty_norm}")

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

# -------------------- Main chatbot reply function --------------------
def get_chatbot_reply(user_text, filepath="database_hosp.csv"):
    entities = extract_entities(user_text)
    if not entities:
        return "Sorry, I couldn't understand your query. Please try rephrasing."

    problem = entities.get("problem")
    doctor = entities.get("doctor")
    hospital = entities.get("hospital")
    location = entities.get("location")

    symptom, true_hospital = extract_symptom_and_hospital(problem, hospital)

    if not symptom:
        return "Sorry, I couldn't identify your health issue. Please rephrase or specify your symptom clearly."

    specialty = specialty_map.get(symptom)
    if not specialty:
        return "Sorry, I couldn't match your symptom to a medical specialty. Please rephrase."

    doctors_primary, doctors_alt = find_doctors(filepath, specialty, true_hospital)

    hospital_display = true_hospital if true_hospital else "Not specified"

    # Compose example-style summary reply
    if doctors_primary:
        doc = doctors_primary[0]
        short_reply = (f"{specialty} → {doc.get('doctor_name')} "
                       f"({doc.get('experience_years')} yrs, {doc.get('area')}, {doc.get('hospital_name')})")
    elif doctors_alt:
        doc = doctors_alt[0]
        short_reply = (f"No. Alternatives → {doc.get('doctor_name')} "
                       f"({doc.get('specialty')}, {doc.get('hospital_name')})")
    else:
        short_reply = "No doctors found for your query."

    # Optionally add detailed info below
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
        response = get_chatbot_reply(user_input, filepath="database_hosp.csv")
        print(response)'''


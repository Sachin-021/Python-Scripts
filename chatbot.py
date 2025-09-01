
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

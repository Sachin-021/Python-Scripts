import os
import re
import csv
from dotenv import load_dotenv
from groq import Groq
from fuzzywuzzy import process

# -------------------- Load environment variables --------------------
load_dotenv()
client = Groq(api_key=os.getenv("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"))  # 👈 store your API key in .env

# -------------------- Symptom → Specialty Mapping --------------------
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

    # ✅ Oncology cases
    "oncology": "Oncology",
    "cancer": "Oncology",
    "tumor": "Oncology",
    "chemotherapy": "Oncology",
    "radiation": "Oncology"
}

# -------------------- Hospital List --------------------
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

# -------------------- Helpers --------------------
def normalize(text):
    """Normalize strings for robust hospital matching."""
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
    """Extract symptom and hospital from user query."""
    user_text_norm = user_text.lower()

    # Symptom
    symptom = fuzzy_extract_best(user_text_norm, list(specialty_map.keys()))

    # Hospital
    hospital_norm_list = [h.lower() for h in hospital_list]
    hospital_match = fuzzy_extract_best(user_text_norm, hospital_norm_list)
    true_hospital = None
    if hospital_match:
        for h in hospital_list:
            if h.lower() == hospital_match:
                true_hospital = h
                break

    return symptom, true_hospital

def find_doctors(filepath, specialty, hospital, max_alts=2):
    """Return doctors from primary hospital and alternative hospitals."""
    doctors_primary, doctors_alt = [], []
    seen_hospitals = set()

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['availability'].strip().lower() != "true":
                continue

            row_hospital_norm = normalize(row['hospital_name'])
            hospital_norm = normalize(hospital) if hospital else None
            row_specialty_norm = row['specialty'].lower()
            specialty_norm = specialty.lower()

            # ✅ Match hospital + specialty
            if hospital_norm and row_hospital_norm == hospital_norm and row_specialty_norm == specialty_norm:
                doctors_primary.append(row)

            # ✅ Alternative hospitals (same specialty, different hospital)
            elif row_specialty_norm == specialty_norm:
                key = (row['hospital_name'], row['area'])
                if key not in seen_hospitals and (not hospital_norm or row_hospital_norm != hospital_norm):
                    doctors_alt.append(row)
                    seen_hospitals.add(key)
                    if len(doctors_alt) == max_alts:
                        break
    return doctors_primary, doctors_alt

def format_doc(row):
    """Format doctor details for display."""
    return (f"Doctor: {row['doctor_name']} | Specialty: {row['specialty']} | "
            f"Experience: {row['experience_years']} yrs | Hospital: {row['hospital_name']} ({row['area']}) | Beds: {row['available_beds']}")

def get_chatbot_reply(user_text, filepath="C:\\Users\\Sachi\\Downloads\\database_hosp.csv"):
    """Main chatbot function."""
    symptom, hospital = extract_symptom_and_hospital(user_text)

    if not symptom:
        return "❌ Sorry, I couldn't identify your health issue. Please rephrase or specify your symptom clearly."

    specialty = specialty_map.get(symptom, None)
    if not specialty:
        return "❌ Sorry, I couldn't match your symptom to a medical specialty."

    doctors_primary, doctors_alt = find_doctors(filepath, specialty, hospital)
    hospital_display = hospital if hospital else "Not specified"

    strict_prompt = f"""
You are a helpful medical chatbot. ONLY use the data provided; do NOT invent details.

User request: "{user_text}"
Symptom: {symptom}
Hospital: {hospital_display}

Doctor(s) at requested hospital:
{format_doc(doctors_primary[0]) if doctors_primary else "None available."}

Alternative hospitals (same specialty, up to 2):
{chr(10).join([format_doc(doc) for doc in doctors_alt]) if doctors_alt else "None available."}

Instructions:
- Clearly recommend available doctors from the requested hospital (if any).
- If none, explain politely and offer up to 2 alternative hospitals/doctors.
- Be friendly, clear, and actionable.
"""
    reply = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": strict_prompt}],
        temperature=0.2
    )
    return reply.choices[0].message.content

# -------------------- Run CLI --------------------
if __name__ == "__main__":
    user_input = input("Ask your health question: ")
    print(get_chatbot_reply(user_input))
import csv
import random

# Existing CSV file
input_file = "database_hosp.csv"
output_file = "database_hosp_extended.csv"

# New hospital locations in Coimbatore
new_locations = [
    "Gandhipuram", "Town Hall", "Singanallur", "Avinashi Road", "Ukkadam", 
    "Saravanampatti", "Kalapatti", "Thudiyalur", "Ganapathy", "Selvapuram",
    "Kuniyamuthur", "Podanur", "Irugur", "Perur", "Chinniampalayam", 
    "Sulur", "Marudamalai", "Kovaipudur"
]

# Specialties to rotate
specialties = [
    "Cardiology", "Oncology", "Neurology", "Orthopedics", "Pediatrics",
    "Dermatology", "Gynecology", "General Medicine", "Gastroenterology",
    "Ophthalmology", "General Surgery"
]

# Doctor name components
first_names = ["Arun", "Priya", "Vijay", "Meena", "Suresh", "Divya", "Karthik", "Anitha", "Rajiv", "Sneha", 
               "Naveen", "Deepa", "Rahul", "Kavitha", "Balaji", "Shalini", "Harini", "Varun", "Rohit", "Ashwin"]
last_names = ["Rao", "Iyer", "Menon", "Krishnan", "Sharma", "Pillai", "Kumar", "Reddy", "Prasad", "Nair"]

# Unique hospital names (extendable)
hospital_name_pool = [
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
    "Sterling Neuro Care", "Cura Medical College", "Radiant Health Care",
    "Pranav Children’s Hospital", "Sri Ramana Eye Institute", "Omega Specialty Hospital",
    "Clover Medical Institute", "Vista Women’s Hospital", "Pulse Heart Care",
    "Magnus General Hospital", "Beacon Health College", "Olive Health Center",
    "Infinity Medical College", "Medicover Specialty Hospital", "Summit Neuro Institute",
    "Serene Women’s Hospital", "Zen Care Hospital", "Divine Health Center",
    "Grace Heart Institute", "Florence Eye Hospital", "Lifecare Children’s Hospital"
]

# Avoid duplicates with existing hospitals
existing_hospitals = set()
with open(input_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        existing_hospitals.add(row["hospital_name"])

hospital_name_pool = [h for h in hospital_name_pool if h not in existing_hospitals]

# Function to generate a new doctor row
def generate_doctor(hospital, area, specialty):
    doctor_name = f"Dr. {random.choice(first_names)} {random.choice(last_names)}"
    experience = random.randint(5, 25)
    availability = random.choice(["True", "False"])
    beds = random.randint(80, 400)
    return {
        "hospital_name": hospital,
        "area": area,
        "doctor_name": doctor_name,
        "specialty": specialty,
        "experience_years": experience,
        "availability": availability,
        "available_beds": beds
    }

# Generate dataset
rows = []
doctors_per_hospital = 5

for hospital_name in hospital_name_pool:
    area = random.choice(new_locations)
    used_specialties = random.sample(specialties, doctors_per_hospital)
    for spec in used_specialties:
        rows.append(generate_doctor(hospital_name, area, spec))

# Save extended dataset
with open(output_file, "w", newline="", encoding="utf-8") as f:
    fieldnames = ["hospital_name","area","doctor_name","specialty","experience_years","availability","available_beds"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    # Append existing dataset
    with open(input_file, "r", encoding="utf-8") as fin:
        for line in fin.readlines()[1:]:
            f.write(line)
    # Append new dataset
    for row in rows:
        writer.writerow(row)

print(f"Extended dataset saved as {output_file} with total {len(rows)} rows (existing + new).")

"""
CardioTwin - Stream 1: Synthetic Indian Patient EHR Generator
Generates clinical EHR profiles tailored for Indian cardiovascular disease demographics,
calculates Framingham risk with South Asian recalibration, and exports to synthetic_patients.json.
"""

import os
import json
import random

try:
    from framingham_risk import calculate_framingham_cvd_risk
except ImportError:
    from backend.framingham_risk import calculate_framingham_cvd_risk



INDIAN_CITIES = [
    ("Mumbai", "Maharashtra"),
    ("Bengaluru", "Karnataka"),
    ("Delhi", "NCR"),
    ("Hyderabad", "Telangana"),
    ("Chennai", "Tamil Nadu"),
    ("Kolkata", "West Bengal"),
    ("Nagpur", "Maharashtra"),
    ("Ahmedabad", "Gujarat"),
    ("Pune", "Maharashtra"),
    ("Kochi", "Kerala"),
    ("Lucknow", "Uttar Pradesh"),
    ("Jaipur", "Rajasthan"),
    ("Bhopal", "Madhya Pradesh"),
    ("Chandigarh", "Punjab"),
    ("Guwahati", "Assam"),
    ("Patna", "Bihar"),
    ("Bhubaneswar", "Odisha"),
    ("Coimbatore", "Tamil Nadu"),
    ("Indore", "Madhya Pradesh"),
    ("Visakhapatnam", "Andhra Pradesh"),
    ("Solapur (Rural District)", "Maharashtra"),
    ("Belagavi (Rural Block)", "Karnataka"),
    ("Varanasi (Tier-2)", "Uttar Pradesh"),
    ("Thrissur", "Kerala")
]

FIRST_NAMES_MALE = [
    "Ramesh", "Rajesh", "Amit", "Suresh", "Vikram", "Sunil", "Anil", "Manoj",
    "Deepak", "Sanjay", "Arjun", "Praveen", "Alok", "Devendra", "Girish",
    "Karthik", "Subhash", "Manish", "Gopal", "Harish", "Sachin", "Vijay", "Rohit"
]
FIRST_NAMES_FEMALE = [
    "Priya", "Sunita", "Anjali", "Meera", "Kavita", "Pooja", "Rekha", "Shalini",
    "Deepa", "Sneha", "Geeta", "Radha", "Nandini", "Anita", "Archana",
    "Lakshmi", "Sarita", "Divya", "Swati", "Ritu", "Bhavna", "Kalyani", "Usha"
]
LAST_NAMES = [
    "Patel", "Sharma", "Verma", "Sen", "Nair", "Iyer", "Rao", "Reddy",
    "Gupta", "Kulkarni", "Deshmukh", "Choudhury", "Bose", "Mehta", "Singh",
    "Banerjee", "Pillai", "Das", "Joshi", "Mishra", "Pandey", "Yadav", "Menon"
]

def generate_patient(patient_id: str, archetype: str = None) -> dict:
    if archetype == "high_risk_male":
        gender = "male"
        age = random.randint(54, 66)
        sbp = random.randint(142, 160)
        dbp = random.randint(88, 98)
        bp_treated = True
        tot_chol = random.randint(220, 260)
        hdl = random.randint(32, 40)
        smoker = True
        diabetes = random.random() < 0.6
        conditions = ["Coronary Artery Disease (Post-PCI)", "Hypertension Stage 2", "Dyslipidemia"]
        medications = [
            {"name": "Metoprolol Succinate", "dosage": "50mg OD", "class": "Beta-Blocker", "hr_effect": -12, "bp_effect": -8},
            {"name": "Atorvastatin", "dosage": "40mg HS", "class": "Statin", "hr_effect": 0, "bp_effect": -2},
            {"name": "Ramipril", "dosage": "5mg OD", "class": "ACE-Inhibitor", "hr_effect": 0, "bp_effect": -12},
            {"name": "Aspirin", "dosage": "75mg OD", "class": "Antiplatelet", "hr_effect": 0, "bp_effect": 0}
        ]
    elif archetype == "diabetic_female":
        gender = "female"
        age = random.randint(46, 56)
        sbp = random.randint(132, 144)
        dbp = random.randint(82, 90)
        bp_treated = True
        tot_chol = random.randint(200, 240)
        hdl = random.randint(38, 48)
        smoker = False
        diabetes = True
        conditions = ["Type 2 Diabetes Mellitus", "Hypertension Stage 1", "Diabetic Dyslipidemia"]
        medications = [
            {"name": "Metformin", "dosage": "500mg BD", "class": "Biguanide", "hr_effect": 0, "bp_effect": 0},
            {"name": "Telmisartan", "dosage": "40mg OD", "class": "ARB", "hr_effect": 0, "bp_effect": -10},
            {"name": "Rosuvastatin", "dosage": "10mg HS", "class": "Statin", "hr_effect": 0, "bp_effect": -2}
        ]
    elif archetype == "elderly_arrhythmia":
        gender = random.choice(["male", "female"])
        age = random.randint(68, 78)
        sbp = random.randint(145, 165)
        dbp = random.randint(80, 92)
        bp_treated = True
        tot_chol = random.randint(190, 230)
        hdl = random.randint(40, 50)
        smoker = random.random() < 0.3
        diabetes = random.random() < 0.4
        conditions = ["Paroxysmal Atrial Fibrillation", "Hypertension Stage 2", "Chronic Kidney Disease Stage 2"]
        medications = [
            {"name": "Bisoprolol", "dosage": "5mg OD", "class": "Beta-Blocker", "hr_effect": -14, "bp_effect": -8},
            {"name": "Apixaban", "dosage": "5mg BD", "class": "DOAC Anticoagulant", "hr_effect": 0, "bp_effect": 0},
            {"name": "Amlodipine", "dosage": "5mg OD", "class": "CCB", "hr_effect": 2, "bp_effect": -10}
        ]
    elif archetype == "young_healthy":
        gender = random.choice(["male", "female"])
        age = random.randint(22, 34)
        sbp = random.randint(112, 122)
        dbp = random.randint(70, 78)
        bp_treated = False
        tot_chol = random.randint(150, 185)
        hdl = random.randint(48, 62)
        smoker = False
        diabetes = False
        conditions = ["None (Healthy Baseline)"]
        medications = []
    else: # General Population Distribution
        gender = random.choice(["male", "female"])
        age = random.randint(30, 68)
        sbp = random.randint(115, 155)
        dbp = int(sbp * 0.62) + random.randint(-4, 6)
        bp_treated = sbp >= 135 and random.random() < 0.7
        tot_chol = random.randint(160, 250)
        hdl = random.randint(35, 58)
        smoker = random.random() < (0.28 if gender == "male" else 0.05)
        diabetes = random.random() < 0.22 # South Asian diabetes prevalence
        conditions = []
        if sbp >= 140: conditions.append("Hypertension Stage 2")
        elif sbp >= 130: conditions.append("Hypertension Stage 1")
        if diabetes: conditions.append("Type 2 Diabetes Mellitus")
        if tot_chol >= 220: conditions.append("Hypercholesterolemia")
        if not conditions: conditions.append("None (Healthy)")
        
        medications = []
        if bp_treated:
            medications.append({"name": "Telmisartan", "dosage": "40mg OD", "class": "ARB", "hr_effect": 0, "bp_effect": -10})
        if tot_chol >= 220:
            medications.append({"name": "Atorvastatin", "dosage": "20mg HS", "class": "Statin", "hr_effect": 0, "bp_effect": -2})

    city, state = random.choice(INDIAN_CITIES)
    first_name = random.choice(FIRST_NAMES_MALE if gender == "male" else FIRST_NAMES_FEMALE)
    last_name = random.choice(LAST_NAMES)
    name = f"{first_name} {last_name}"

    # Calculate Layer 1 Framingham Risk
    risk_info = calculate_framingham_cvd_risk(
        age=age,
        gender=gender,
        systolic_bp=sbp,
        bp_treated=bp_treated,
        total_cholesterol=tot_chol,
        hdl_cholesterol=hdl,
        smoker=smoker,
        diabetes=diabetes,
        is_south_asian=True
    )

    resting_hr = random.randint(62, 84)
    # If on beta blocker, reduce resting HR
    for m in medications:
        resting_hr += m.get("hr_effect", 0)

    bmi = round(random.uniform(21.5, 31.0), 1)

    return {
        "id": patient_id,
        "name": name,
        "age": age,
        "gender": gender,
        "city": city,
        "state": state,
        "vitals": {
            "resting_hr": max(52, resting_hr),
            "systolic_bp": sbp,
            "diastolic_bp": dbp,
            "bp_treated": bp_treated,
            "bmi": bmi,
            "spo2_baseline": random.randint(96, 99)
        },
        "labs": {
            "total_cholesterol": tot_chol,
            "hdl_cholesterol": hdl,
            "ldl_cholesterol": max(60, tot_chol - hdl - 30),
            "triglycerides": random.randint(120, 240),
            "fasting_glucose": random.randint(130, 185) if diabetes else random.randint(82, 100),
            "hba1c": round(random.uniform(7.1, 9.4), 1) if diabetes else round(random.uniform(5.1, 5.6), 1),
            "hs_crp": round(random.uniform(1.8, 4.5), 2) if "Coronary" in str(conditions) else round(random.uniform(0.4, 1.5), 2)
        },
        "lifestyle": {
            "smoker": smoker,
            "physical_activity": random.choice(["Sedentary", "Moderate (Walking)", "Active"]),
            "diet": random.choice(["Vegetarian (High Carb)", "Non-Vegetarian", "Jain Diet", "Balanced"])
        },
        "clinical_history": {
            "conditions": conditions,
            "medications": medications,
            "allergies": ["None known"] if random.random() < 0.85 else ["Penicillin"]
        },
        "cardiovascular_risk": risk_info
    }

def generate_cohort(num_patients: int = 100, output_file: str = "synthetic_patients.json"):
    patients = []
    
    # 5 Handcrafted Key Archetypes for Demos
    archetypes = [
        ("PAT001", "high_risk_male"),
        ("PAT002", "diabetic_female"),
        ("PAT003", "elderly_arrhythmia"),
        ("PAT004", "young_healthy"),
        ("PAT005", "general")
    ]
    for pid, arch in archetypes:
        patients.append(generate_patient(pid, arch))

    # Generate remaining cohort
    for i in range(len(patients) + 1, num_patients + 1):
        pid = f"PAT{i:04d}" if num_patients > 999 else f"PAT{i:03d}"
        patients.append(generate_patient(pid))

    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(patients, f, indent=2)

    print(f"Generated {len(patients)} synthetic Indian patient EHR records saved to '{output_file}'.")
    return patients


def generate_cohort_summary(patients: list, summary_file: str = "docs/synthetic_cohort_summary.json"):
    total = len(patients)
    males = sum(1 for p in patients if p["gender"] == "male")
    females = total - males
    ages = [p["age"] for p in patients]
    risks = [p.get("cardiovascular_risk", {}).get("risk_category", "Unknown") for p in patients]
    diabetes_count = sum(1 for p in patients if any("Diabetes" in c for c in p.get("clinical_history", {}).get("conditions", [])))
    smokers = sum(1 for p in patients if p.get("lifestyle", {}).get("smoker", False))
    hypertensive = sum(1 for p in patients if any("Hypertension" in c for c in p.get("clinical_history", {}).get("conditions", [])))

    risk_dist = {}
    for r in risks:
        risk_dist[r] = risk_dist.get(r, 0) + 1

    summary = {
        "total_cohort_size": total,
        "demographics": {
            "males": males,
            "male_pct": round((males / total) * 100, 1),
            "females": females,
            "female_pct": round((females / total) * 100, 1),
            "mean_age": round(float(sum(ages) / total), 1),
            "age_range": [min(ages), max(ages)]
        },
        "cardiometabolic_prevalence": {
            "hypertension_cases": hypertensive,
            "hypertension_pct": round((hypertensive / total) * 100, 1),
            "type2_diabetes_cases": diabetes_count,
            "type2_diabetes_pct": round((diabetes_count / total) * 100, 1),
            "tobacco_smoker_cases": smokers,
            "tobacco_smoker_pct": round((smokers / total) * 100, 1)
        },
        "recalibrated_framingham_risk_distribution": risk_dist,
        "south_asian_factor_applied": 1.45,
        "geographic_coverage": "24 Indian urban metropolitan centers, tier-2 cities, and rural district blocks"
    }

    os.makedirs(os.path.dirname(summary_file) if os.path.dirname(summary_file) else ".", exist_ok=True)
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved cohort demographic summary ({total} patients) to '{summary_file}'.")
    return summary


if __name__ == "__main__":
    # 1. Maintain standard 100-patient cohort for default API contract
    patients_100 = generate_cohort(100, "backend/synthetic_patients.json")
    # Also save at root if needed
    generate_cohort(100, "synthetic_patients.json")

    # 2. Generate scaled 4,000-patient epidemiological cohort (Phase 5.3)
    patients_4000 = generate_cohort(4000, "data/processed/synthetic_patients_4000.json")
    generate_cohort_summary(patients_4000, "docs/synthetic_cohort_4000_summary.json")


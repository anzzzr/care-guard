"""Create all tables and load synthetic plans, members and claims.

Run from the project root:  uv run python -m scripts.seed

All data is made up. Re-running replaces members, claims, tickets and logs.
Policy chunks are left alone (scripts/ingest.py owns them).
"""

from datetime import date

import psycopg

from app.db import connect, create_tables

PLANS = [
    # id, name, sum_insured (₹), policy_doc_file
    ("basic", "Sahay Basic", 300_000, "sahay_basic.md"),
    ("plus", "Sahay Plus", 1_000_000, "sahay_plus.md"),
    ("senior", "Sahay Senior", 500_000, "sahay_senior.md"),
]

MEMBERS = [
    # id, name, api_key, plan_id, policy_start_date, age
    ("M001", "Asha Demo", "demo-key-m001", "basic", date(2025, 4, 1), 34),
    ("M002", "Ravi Sample", "demo-key-m002", "basic", date(2023, 1, 15), 62),
    ("M003", "Meera Testcase", "demo-key-m003", "basic", date(2026, 2, 1), 41),
    ("M004", "Karan Placeholder", "demo-key-m004", "basic", date(2024, 7, 10), 29),
    ("M005", "Priya Fakename", "demo-key-m005", "plus", date(2025, 9, 1), 38),
    ("M006", "Arjun Mock", "demo-key-m006", "plus", date(2022, 5, 20), 45),
    ("M007", "Neha Dummy", "demo-key-m007", "plus", date(2024, 11, 1), 31),
    ("M008", "Suresh Example", "demo-key-m008", "senior", date(2025, 1, 10), 67),
    ("M009", "Lakshmi Sample", "demo-key-m009", "senior", date(2023, 8, 1), 72),
    ("M010", "Gopal Testuser", "demo-key-m010", "senior", date(2026, 3, 15), 64),
]

SUNRISE = "Sunrise Multispeciality Hospital, Pune"
LOTUS = "Lotus City Hospital, Nagpur"
RIVERBANK = "Riverbank Medical Centre, Kochi"
GREENFIELD = "Greenfield Hospital, Jaipur"
HARBOURVIEW = "Harbourview Heart Institute, Mumbai"
SILVER_OAK = "Silver Oak Hospital, Bengaluru"
CITY_CARE = "City Care Clinic, Indore"  # not a network hospital

CLAIMS = [
    # id, member_id, hospital, procedure, claimed, approved, status, rejection_reason, submitted_on
    # --- Basic plan (₹3,00,000; room rent cap ₹3,000/day; 20% co-pay at 60+) ---
    (
        "CLM-1001",
        "M001",
        SUNRISE,
        "Appendectomy",
        85_000,
        85_000,
        "approved",
        None,
        date(2025, 8, 12),
    ),
    (
        "CLM-1002",
        "M001",
        SUNRISE,
        "Cataract surgery (right eye)",
        45_000,
        0,
        "rejected",
        "Cataract surgery has a 2-year waiting period (Basic Plan Section 4.3). Policy started on "
        "2025-04-01, so the waiting period was not completed.",
        date(2026, 5, 20),
    ),
    (
        "CLM-1003",
        "M001",
        LOTUS,
        "Dengue fever hospitalisation",
        60_000,
        42_000,
        "partially_approved",
        "Room rent of ₹5,000/day exceeded the ₹3,000/day limit (1% of sum insured). Proportionate "
        "deduction applied to associated medical expenses (Basic Plan Section 3.2).",
        date(2026, 9, 3),
    ),
    (
        "CLM-1004",
        "M002",
        SUNRISE,
        "Knee replacement (left knee)",
        240_000,
        192_000,
        "partially_approved",
        "20% co-payment applies because the member is aged 60 or above (Basic Plan Section 5.1).",
        date(2025, 6, 18),
    ),
    (
        "CLM-1005",
        "M002",
        GREENFIELD,
        "Pneumonia hospitalisation",
        70_000,
        56_000,
        "partially_approved",
        "20% co-payment applies because the member is aged 60 or above (Basic Plan Section 5.1).",
        date(2026, 1, 22),
    ),
    (
        "CLM-1006",
        "M002",
        CITY_CARE,
        "Dental implant",
        35_000,
        0,
        "rejected",
        "Dental treatment is excluded unless it needs hospitalisation because of an accident "
        "(Basic Plan Section 7.2).",
        date(2026, 7, 9),
    ),
    (
        "CLM-1007",
        "M003",
        LOTUS,
        "Viral fever hospitalisation",
        25_000,
        0,
        "rejected",
        "Illness started within the initial 30-day waiting period; policy started on 2026-02-01 "
        "and admission was on 2026-02-18 (Basic Plan Section 4.1).",
        date(2026, 2, 25),
    ),
    (
        "CLM-1008",
        "M003",
        LOTUS,
        "Fracture treatment after road accident",
        55_000,
        55_000,
        "approved",
        None,
        date(2026, 2, 20),
    ),
    (
        "CLM-1009",
        "M003",
        SUNRISE,
        "Gallbladder removal (laparoscopic)",
        90_000,
        None,
        "pending",
        None,
        date(2026, 11, 10),
    ),
    (
        "CLM-1010",
        "M004",
        GREENFIELD,
        "Kidney stone removal (lithotripsy, day-care)",
        40_000,
        40_000,
        "approved",
        None,
        date(2026, 9, 5),
    ),
    (
        "CLM-1011",
        "M004",
        CITY_CARE,
        "Rhinoplasty (cosmetic nose surgery)",
        120_000,
        0,
        "rejected",
        "Cosmetic or aesthetic treatment is excluded (Basic Plan Section 7.1).",
        date(2025, 12, 1),
    ),
    (
        "CLM-1012",
        "M004",
        GREENFIELD,
        "Typhoid hospitalisation",
        38_000,
        34_500,
        "partially_approved",
        "Non-medical items (toiletries, attendant charges) of ₹3,500 are not payable "
        "(Claims Process Section 5.1).",
        date(2025, 10, 14),
    ),
    (
        "CLM-1013",
        "M004",
        CITY_CARE,
        "OPD consultation and blood tests",
        4_500,
        0,
        "rejected",
        "Out-patient (OPD) treatment without hospitalisation is not covered "
        "(Basic Plan Section 7.4).",
        date(2026, 3, 2),
    ),
    # --- Plus plan (₹10,00,000; no room rent cap; 2-year listed-procedure wait) ---
    (
        "CLM-1014",
        "M005",
        SILVER_OAK,
        "Hernia repair",
        110_000,
        0,
        "rejected",
        "Hernia repair has a 2-year waiting period (Plus Plan Section 4.3). Policy started on "
        "2025-09-01, so the waiting period was not completed.",
        date(2026, 7, 14),
    ),
    (
        "CLM-1015",
        "M005",
        SILVER_OAK,
        "Malaria hospitalisation (single private room)",
        95_000,
        95_000,
        "approved",
        None,
        date(2026, 4, 28),
    ),
    (
        "CLM-1016",
        "M005",
        SILVER_OAK,
        "Maternity (normal delivery)",
        70_000,
        0,
        "rejected",
        "Maternity has a 3-year waiting period (Plus Plan Section 6.1). Policy started on "
        "2025-09-01, so the waiting period was not completed.",
        date(2026, 10, 6),
    ),
    (
        "CLM-1017",
        "M006",
        HARBOURVIEW,
        "Coronary angioplasty",
        380_000,
        380_000,
        "approved",
        None,
        date(2025, 3, 11),
    ),
    (
        "CLM-1018",
        "M006",
        RIVERBANK,
        "Cataract surgery (both eyes)",
        120_000,
        100_000,
        "partially_approved",
        "Cataract surgery is covered up to ₹50,000 per eye (Plus Plan Section 5.2).",
        date(2026, 2, 16),
    ),
    (
        "CLM-1019",
        "M006",
        RIVERBANK,
        "Spectacles after cataract surgery",
        12_000,
        0,
        "rejected",
        "Spectacles and contact lenses are excluded (Plus Plan Section 7.3).",
        date(2026, 3, 4),
    ),
    (
        "CLM-1020",
        "M006",
        HARBOURVIEW,
        "Chemotherapy (day-care, 3 cycles)",
        150_000,
        None,
        "pending",
        None,
        date(2026, 11, 15),
    ),
    (
        "CLM-1021",
        "M007",
        SILVER_OAK,
        "Knee arthroscopy",
        140_000,
        0,
        "rejected",
        "Knee surgery, including arthroscopy, has a 2-year waiting period (Plus Plan Section 4.3). "
        "Policy started on 2024-11-01 and admission was on 2026-06-03.",
        date(2026, 6, 10),
    ),
    (
        "CLM-1022",
        "M007",
        SUNRISE,
        "Food poisoning hospitalisation",
        32_000,
        29_000,
        "partially_approved",
        "Separately billed disposable consumables of ₹3,000 are not payable "
        "(Claims Process Section 5.1).",
        date(2025, 12, 27),
    ),
    (
        "CLM-1023",
        "M007",
        SUNRISE,
        "Appendectomy",
        105_000,
        105_000,
        "approved",
        None,
        date(2026, 8, 19),
    ),
    # --- Senior plan (₹5,00,000; 30% co-pay; 1-year pre-existing disease wait) ---
    (
        "CLM-1024",
        "M008",
        LOTUS,
        "Diabetes complication hospitalisation (pre-existing)",
        80_000,
        0,
        "rejected",
        "Pre-existing disease has a 1-year waiting period (Senior Plan Section 4.2). "
        "Policy started on 2025-01-10 and admission was on 2025-10-28.",
        date(2025, 11, 2),
    ),
    (
        "CLM-1025",
        "M008",
        LOTUS,
        "Hip fracture surgery after a fall",
        200_000,
        140_000,
        "partially_approved",
        "30% co-payment applies to every claim (Senior Plan Section 5.1).",
        date(2026, 5, 7),
    ),
    (
        "CLM-1026",
        "M008",
        GREENFIELD,
        "Hypertension-related hospitalisation (pre-existing)",
        60_000,
        42_000,
        "partially_approved",
        "30% co-payment applies to every claim (Senior Plan Section 5.1).",
        date(2026, 8, 30),
    ),
    (
        "CLM-1027",
        "M009",
        RIVERBANK,
        "Cataract surgery (left eye)",
        55_000,
        28_000,
        "partially_approved",
        "Cataract is covered up to ₹40,000 per eye (Senior Plan Section 5.2); 30% co-payment was "
        "then applied to ₹40,000 (Senior Plan Section 5.1).",
        date(2025, 11, 19),
    ),
    (
        "CLM-1028",
        "M009",
        RIVERBANK,
        "Pneumonia hospitalisation",
        100_000,
        49_000,
        "partially_approved",
        "Room rent of ₹8,000/day exceeded the ₹5,000/day limit, so a proportionate deduction "
        "reduced the payable amount to ₹70,000 (Senior Plan Section 3.2); 30% co-payment was then "
        "applied (Senior Plan Section 5.1).",
        date(2026, 6, 24),
    ),
    (
        "CLM-1029",
        "M009",
        CITY_CARE,
        "Physiotherapy at home",
        18_000,
        0,
        "rejected",
        "Treatment at home, including home physiotherapy, is excluded (Senior Plan Section 7.5).",
        date(2026, 9, 12),
    ),
    (
        "CLM-1030",
        "M010",
        GREENFIELD,
        "Prostate surgery (TURP)",
        130_000,
        None,
        "pending",
        None,
        date(2026, 11, 18),
    ),
    (
        "CLM-1031",
        "M010",
        GREENFIELD,
        "Bronchitis hospitalisation",
        45_000,
        31_500,
        "partially_approved",
        "30% co-payment applies to every claim (Senior Plan Section 5.1).",
        date(2026, 7, 21),
    ),
]


def seed(conn: psycopg.Connection) -> None:
    create_tables(conn)
    conn.execute("TRUNCATE request_logs, review_tickets, claims, members, plans RESTART IDENTITY")
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO plans VALUES (%s, %s, %s, %s)", PLANS)
        cur.executemany("INSERT INTO members VALUES (%s, %s, %s, %s, %s, %s)", MEMBERS)
        cur.executemany("INSERT INTO claims VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", CLAIMS)


def main() -> None:
    with connect() as conn:
        seed(conn)
    print(f"Seeded {len(PLANS)} plans, {len(MEMBERS)} members, {len(CLAIMS)} claims.")


if __name__ == "__main__":
    main()

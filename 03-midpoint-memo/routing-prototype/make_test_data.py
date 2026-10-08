"""Usage: python3 make_test_data.py [OUT_DIR]

Generate synthetic lawn-sign requests and captains CSVs that mirror the JBR sheet layout.

Real street names in each town, fictional house numbers and residents.
A few rows are deliberately unroutable (fake streets) to exercise geocode-failure reporting.
"""
import csv
import os
import random
import sys
from datetime import datetime, timedelta

random.seed(371)
OUT = sys.argv[1] if len(sys.argv) > 1 else "."

TOWNS = {
    "Duxbury": ("02332", ["Washington St", "Tremont St", "Bay Rd", "Summer St", "Depot St",
                          "Franklin St", "Chestnut St", "St George St", "Union St", "Lincoln St"]),
    "Halifax": ("02338", ["Plymouth St", "Monponsett St", "Holmes St", "Thompson St", "South St",
                          "River St", "Elm St"]),
    "Hanson": ("02341", ["Main St", "Liberty St", "Indian Head St", "Spring St", "High St",
                         "Winter St", "Pleasant St", "East Washington St"]),
    "Marshfield": ("02050", ["Ocean St", "Main St", "Plain St", "Union St", "Furnace St",
                             "Careswell St", "Moraine St", "Webster St", "Highland St"]),
    "Pembroke": ("02359", ["Center St", "Washington St", "Oldham St", "Mattakeesett St",
                           "Plymouth St", "School St", "Union St", "High St"]),
}
PRECINCTS = {"Duxbury": ["1", "2", "3"], "Halifax": ["2"], "Hanson": ["2", "3"],
             "Marshfield": ["2A", "4"], "Pembroke": ["1", "2"]}
FAKE_STREETS = {"Duxbury": "Moonbeam Terrace", "Pembroke": "Quillfeather Way"}

FIRST = ["Alex", "Jordan", "Casey", "Morgan", "Riley", "Taylor", "Jamie", "Avery", "Quinn", "Reese",
         "Drew", "Sam", "Robin", "Kendall", "Parker", "Hayden", "Skyler", "Emerson", "Rowan", "Blake"]
LAST = ["Testwell", "Sampleton", "Mockford", "Demoson", "Fakely", "Placeholder", "Trialby",
        "Pilotson", "Exampleton", "Synthwood"]

HEADER = ["Request ID", "Submitted Date", "Full Name", "Phone Number", "Email", "Street Address",
          "Town", "ZIP", "Precinct", "Number of Signs", "Preferred Delivery", "Installation Authorized",
          "Delivery Status", "Volunteer", "Delivery Date", "Delivery Confirmed", "Pickup Requested",
          "Pickup Status", "Comments"]

rows = []
start = datetime(2026, 9, 10, 9, 0)
n = 0
for town, (zipc, streets) in TOWNS.items():
    for i in range(20):
        n += 1
        street = random.choice(streets)
        num = random.randint(10, 400)
        addr = f"{num} {street}"
        if town in FAKE_STREETS and i == 7:
            addr = f"{random.randint(10, 99)} {FAKE_STREETS[town]}"
        authorized = "No" if random.random() < 0.15 else "Yes"
        status = random.choices(["Pending", "Scheduled", "Delivered", "delivered"],
                                weights=[45, 20, 25, 5])[0]
        delivered = status.lower() == "delivered"
        submitted = start + timedelta(hours=random.randint(0, 24 * 25))
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        rows.append([
            f"REQ-{n:04d}", submitted.strftime("%Y-%m-%d %H:%M"), name,
            f"781-555-01{random.randint(0, 99):02d}", f"test+req{n:04d}@example.com",
            addr, town, zipc, random.choice(PRECINCTS[town]), random.choice([1, 1, 1, 2, 2, 3]),
            random.choice(["Anytime", "Weekday", "Weekend"]), authorized, status,
            "", (submitted + timedelta(days=3)).strftime("%Y-%m-%d") if delivered else "",
            "Yes" if delivered else "", "No", "", "Synthetic proof-of-concept record.",
        ])

with open(os.path.join(OUT, "test_lawn_sign_requests.csv"), "w", newline="") as f:
    w = csv.writer(f)
    blank = [""] * (len(HEADER) - 1)
    w.writerow(["JBR Lawn Sign Requests"] + blank)
    w.writerow(["Synthetic test records for workflow testing only. Names, phones, emails, "
                "and street numbers are fictional."] + blank)
    w.writerow(["Generated for routing proof of concept | Created 2026-10-08"] + blank)
    w.writerow(HEADER)
    w.writerows(rows)

with open(os.path.join(OUT, "test_captains.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Town", "Captain Name", "Captain Email", "Token", "Active"])
    for i, town in enumerate(TOWNS, 1):
        w.writerow([town, f"Volunteer {i} Test", f"test+captain{i}@example.com",
                    "%032x" % random.getrandbits(128), "Yes"])

print(f"wrote {len(rows)} requests, {len(TOWNS)} captains")

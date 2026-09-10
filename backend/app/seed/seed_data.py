"""Deterministic Phase 1 seed data: entities, reference data, and the five
demo accounts. A faithful port of `frontend/src/services/seed.js` for the
tables Phase 1 owns — see BUILDPHASES.md "Seed data spec".

Everything here is a plain data description, no I/O and no randomness — the
determinism the demo depends on comes from this module containing fixed
values, not from a seeded PRNG. `app.seed.reset` turns this into ORM rows
and generated credentials (password hash, Ed25519 keypair).

Deviation from `seed.js`'s *runtime* agent/vehicle counts: the frontend
script's loop computes 10 agents and 7 vehicles across 3 distributors, but
BUILDPHASES.md's seed data spec table — the documented source of truth for
Phase 1 — calls for 7 agents and 5 vehicles. This module follows the
documented counts. `agent_1` = Ravi Kumar on `dist_1` and `dist_1` = Sunrise
Pharma Distributors are unchanged either way, which is what the demo path
actually depends on.
"""
from __future__ import annotations

from typing import TypedDict


class PharmacySeed(TypedDict):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    address: str
    license_no: str
    phone: str


class DistributorSeed(TypedDict):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    address: str
    license_no: str


class ManufacturerSeed(TypedDict):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    address: str
    license_no: str


class FacilitySeed(TypedDict):
    id: str
    name: str
    city: str
    lat: float
    lng: float
    license_no: str


class AgentSeed(TypedDict):
    id: str
    distributor_id: str
    name: str
    phone: str


class VehicleSeed(TypedDict):
    id: str
    distributor_id: str
    reg_no: str


class DrugSeed(TypedDict):
    key: str
    name: str
    category: str
    price: str


class DemoUserSeed(TypedDict):
    id: str
    email: str
    name: str
    role: str
    entity_id: str


# ---- Pharmacies (10) — TN-RTL-20250+ ---------------------------------------

_PHARMACY_NAMES = [
    ("Apollo Pharmacy — T. Nagar", "Chennai", 13.0418, 80.2341),
    ("MedPlus — Anna Nagar", "Chennai", 13.0878, 80.2101),
    ("Sri Krishna Medicals", "Chennai", 13.0604, 80.2496),
    ("Vijaya Pharma — Velachery", "Chennai", 12.9791, 80.2209),
    ("Guardian Chemists", "Chennai", 13.0067, 80.2570),
    ("Annai Medical Store", "Coimbatore", 11.0168, 76.9558),
    ("Saravana Pharma", "Madurai", 9.9252, 78.1198),
    ("Kaveri Medicals", "Tiruchirappalli", 10.7905, 78.7047),
    ("Bharathi Drug House", "Salem", 11.6643, 78.1460),
    ("Lakshmi Pharmacy — Adyar", "Chennai", 13.0012, 80.2565),
]

PHARMACIES: list[PharmacySeed] = [
    {
        "id": f"ph_{i + 1}",
        "name": name,
        "city": city,
        "lat": lat,
        "lng": lng,
        "address": f"{10 + i} {city} Main Rd, {city}, Tamil Nadu",
        "license_no": f"TN-RTL-{20250 + i}",
        "phone": f"+91 98{str(40000000 + i * 111111)[:8]}",
    }
    for i, (name, city, lat, lng) in enumerate(_PHARMACY_NAMES)
]

# ---- Distributors (3) — dist_1 = Sunrise Pharma Distributors ---------------

_DISTRIBUTOR_NAMES = [
    ("Sunrise Pharma Distributors", "Chennai", 13.0850, 80.2101),
    ("Meridian Medical Logistics", "Chennai", 12.9900, 80.2200),
    ("TN Healthcare Supply Co.", "Coimbatore", 11.0100, 76.9600),
]

DISTRIBUTORS: list[DistributorSeed] = [
    {
        "id": f"dist_{i + 1}",
        "name": name,
        "city": city,
        "lat": lat,
        "lng": lng,
        "address": f"{city} Wholesale Market, {city}, Tamil Nadu",
        "license_no": f"TN-DST-{1200 + i}",
    }
    for i, (name, city, lat, lng) in enumerate(_DISTRIBUTOR_NAMES)
]

# ---- Manufacturers (4) — mfr_1 = Cipla Ltd. --------------------------------

_MANUFACTURER_NAMES = [
    ("Cipla Ltd.", "Chennai", 13.1100, 80.1000),
    ("Sun Pharmaceutical Industries", "Chennai", 12.9500, 80.1500),
    ("Dr. Reddy's Laboratories", "Chennai", 13.0500, 80.1800),
    ("Zydus Lifesciences", "Coimbatore", 11.0500, 76.9000),
]

MANUFACTURERS: list[ManufacturerSeed] = [
    {
        "id": f"mfr_{i + 1}",
        "name": name,
        "city": city,
        "lat": lat,
        "lng": lng,
        "address": f"{city} Industrial Estate, {city}, Tamil Nadu",
        "license_no": f"MFG-{5500 + i}",
    }
    for i, (name, city, lat, lng) in enumerate(_MANUFACTURER_NAMES)
]

# ---- Facilities (3) ---------------------------------------------------------

_FACILITY_NAMES = [
    ("Medicare Biomedical Waste Facility", "Gummidipoondi", 13.4080, 80.1100),
    ("EnviroSafe Incineration Unit", "Sriperumbudur", 12.9700, 79.9400),
    ("GreenClean Waste Management", "Maraimalai Nagar", 12.7900, 80.0200),
]

FACILITIES: list[FacilitySeed] = [
    {
        "id": f"fac_{i + 1}",
        "name": name,
        "city": city,
        "lat": lat,
        "lng": lng,
        "license_no": f"BMW-{900 + i}",
    }
    for i, (name, city, lat, lng) in enumerate(_FACILITY_NAMES)
]

# ---- Regulator (1) — reg_1 = CDSCO — Tamil Nadu ----------------------------

REGULATOR = {
    "id": "reg_1",
    "name": "CDSCO — Tamil Nadu",
    "jurisdiction": "Tamil Nadu",
    "officer_name": "R. Menon",
    "officer_designation": "Assistant Drug Controller",
    "officer_id": "CDSCO-TN-4471",
}

# ---- Agents (7) — agent_1 = Ravi Kumar, on dist_1 --------------------------

_AGENT_NAMES = ["Ravi Kumar", "Suresh Babu", "Karthik M.", "Anand R.", "Vignesh S.", "Prakash T.", "Manoj K."]
# 3 on dist_1, 2 on dist_2, 2 on dist_3 — 7 total, matching the seed spec.
_AGENT_DISTRIBUTOR_SPREAD = ["dist_1", "dist_1", "dist_1", "dist_2", "dist_2", "dist_3", "dist_3"]

AGENTS: list[AgentSeed] = [
    {
        "id": f"agent_{i + 1}",
        "distributor_id": _AGENT_DISTRIBUTOR_SPREAD[i],
        "name": name,
        "phone": f"+91 90{str(43000000 + i * 131313)[:8]}",
    }
    for i, name in enumerate(_AGENT_NAMES)
]

# ---- Vehicles (5) -----------------------------------------------------------

# 2 on dist_1, 2 on dist_2, 1 on dist_3 — 5 total, matching the seed spec.
_VEHICLE_DISTRIBUTOR_SPREAD = ["dist_1", "dist_1", "dist_2", "dist_2", "dist_3"]

VEHICLES: list[VehicleSeed] = [
    {
        "id": f"veh_{i + 1}",
        "distributor_id": _VEHICLE_DISTRIBUTOR_SPREAD[i],
        "reg_no": f"TN {11 + i} AB {1000 + i * 37}",
    }
    for i in range(5)
]

# ---- Drugs (9) --------------------------------------------------------------

DRUGS: list[DrugSeed] = [
    {"key": "DOX", "name": "Doxorubicin 50mg", "category": "oncology", "price": "4200.00"},
    {"key": "CIS", "name": "Cisplatin 50mg", "category": "oncology", "price": "3800.00"},
    {"key": "CEF", "name": "Cefixime 200mg", "category": "antibiotics", "price": "320.00"},
    {"key": "MER", "name": "Meropenem 1g Inj", "category": "antibiotics", "price": "1450.00"},
    {"key": "ATO", "name": "Atorvastatin 20mg", "category": "cardiovascular", "price": "180.00"},
    {"key": "AML", "name": "Amlodipine 5mg", "category": "cardiovascular", "price": "95.00"},
    {"key": "PAR", "name": "Paracetamol 650mg", "category": "other", "price": "40.00"},
    {"key": "MET", "name": "Metformin 500mg", "category": "other", "price": "65.00"},
    {"key": "OME", "name": "Omeprazole 20mg", "category": "other", "price": "88.00"},
]

# ---- Demo users (5) — DEMO_ACCOUNTS in frontend/src/store/authStore.js ----

DEMO_USERS: list[DemoUserSeed] = [
    {"id": "usr_retailer", "email": "retailer@dot.in", "name": "Apollo Pharmacy — T. Nagar",
     "role": "RETAILER", "entity_id": "ph_1"},
    {"id": "usr_distributor", "email": "distributor@dot.in", "name": "Sunrise Pharma Distributors",
     "role": "DISTRIBUTOR", "entity_id": "dist_1"},
    {"id": "usr_agent", "email": "agent@dot.in", "name": "Ravi Kumar",
     "role": "PICKUP_AGENT", "entity_id": "agent_1"},
    {"id": "usr_manufacturer", "email": "manufacturer@dot.in", "name": "Cipla Ltd.",
     "role": "MANUFACTURER", "entity_id": "mfr_1"},
    {"id": "usr_regulator", "email": "regulator@dot.in", "name": "CDSCO — Tamil Nadu",
     "role": "REGULATOR", "entity_id": "reg_1"},
]

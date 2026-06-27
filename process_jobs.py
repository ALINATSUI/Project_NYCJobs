#!/usr/bin/env python3
"""
Processes raw job data from public-sector-raw.json and private-sector-raw.json.

Extracts skills using ojd_daps_skills (Lightcast taxonomy) and outputs a unified
schema to jobs-processed.parquet for use with a DuckDB-wasm frontend dashboard.

Usage:
    python process_jobs.py

Dependencies:
    pip install ojd-daps-skills pyarrow pandas
"""

import json
import os
import re
from datetime import date, datetime
from typing import Optional

import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────

PUBLIC_RAW  = "public-sector-raw.json"
PRIVATE_RAW = "private-sector-raw.json"
OUTPUT_FILE = "jobs-processed.parquet"
CHECKPOINT  = "jobs-processed-checkpoint.json"

SKILL_BATCH_SIZE  = 256
CHECKPOINT_EVERY  = 1000
TAXONOMY          = "lightcast"

# ── Borough detection ──────────────────────────────────────────────────────────

# Ordered so longer/more-specific strings are matched first
_BOROUGH_PATTERNS: list[tuple[str, str]] = [
    ("staten island",    "Staten Island"),
    ("st. george",       "Staten Island"),
    ("st george",        "Staten Island"),
    ("new dorp",         "Staten Island"),
    ("tottenville",      "Staten Island"),
    ("long island city", "Queens"),
    ("lic",              "Queens"),
    ("l i city",         "Queens"),
    ("flushing",         "Queens"),
    ("astoria",          "Queens"),
    ("jamaica",          "Queens"),
    ("maspeth",          "Queens"),
    ("corona",           "Queens"),
    ("jackson heights",  "Queens"),
    ("forest hills",     "Queens"),
    ("woodside",         "Queens"),
    ("ridgewood",        "Queens"),
    ("south bronx",      "Bronx"),
    ("the bronx",        "Bronx"),
    (" bronx",           "Bronx"),
    ("bx ",              "Bronx"),
    ("bx.",              "Bronx"),
    ("bxhqt",            "Bronx"),
    ("pelham",           "Bronx"),
    ("hunts point",      "Bronx"),
    ("fordham",          "Bronx"),
    ("williamsburg",     "Brooklyn"),
    ("bushwick",         "Brooklyn"),
    ("flatbush",         "Brooklyn"),
    ("bay ridge",        "Brooklyn"),
    ("coney island",     "Brooklyn"),
    ("park slope",       "Brooklyn"),
    ("bklyn",            "Brooklyn"),
    ("brooklyn",         "Brooklyn"),
    ("harlem",           "Manhattan"),
    ("washington heights","Manhattan"),
    ("inwood",           "Manhattan"),
    ("midtown",          "Manhattan"),
    ("downtown",         "Manhattan"),
    ("lower manhattan",  "Manhattan"),
    ("world trade",      "Manhattan"),
    ("financial district","Manhattan"),
    ("tribeca",          "Manhattan"),
    ("soho",             "Manhattan"),
    ("chelsea",          "Manhattan"),
    ("upper east side",  "Manhattan"),
    ("upper west side",  "Manhattan"),
    ("manhattan",        "Manhattan"),
    # Abbreviations used in OpenData locations
    ("n.y.",             "Manhattan"),
    (" ny,",             "Manhattan"),
    ("nyc",              "Manhattan"),
    ("queens",           "Queens"),
    ("bronx",            "Bronx"),
]


def detect_borough(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    for keyword, borough in _BOROUGH_PATTERNS:
        if keyword in t:
            return borough
    return None


# ── Employment type normalization ──────────────────────────────────────────────

def normalize_employment_type(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    t = raw.lower()
    if "intern" in t:
        return "internship"
    if "volunteer" in t:
        return "volunteer"
    if "per diem" in t or "per-diem" in t:
        return "per_diem"
    if "temp" in t or "seasonal" in t:
        return "temporary"
    if "contract" in t or "freelance" in t or "consultant" in t:
        return "contract"
    if "part" in t:
        return "part_time"
    if "full" in t:
        return "full_time"
    return "other"


# ── Salary normalization ───────────────────────────────────────────────────────

_PERIOD_MULTIPLIERS = {
    "year":   1,
    "annual": 1,
    "hour":   2080,
    "hourly": 2080,
    "day":    260,
    "daily":  260,
    "week":   52,
    "weekly": 52,
    "month":  12,
}


def normalize_period(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    t = raw.lower()
    for key in ("year", "annual", "hour", "day", "week", "month"):
        if key in t:
            return key
    return None


def to_annual(amount: Optional[float], period: Optional[str]) -> Optional[float]:
    if amount is None or period is None:
        return None
    mult = _PERIOD_MULTIPLIERS.get(period.lower())
    return round(amount * mult, 2) if mult else None


# ── Education level extraction ─────────────────────────────────────────────────

_EDU_PATTERNS = [
    (r"\bdoctor(?:ate|al)?\b|\bph\.?d\b",                             "doctorate"),
    (r"\bmaster(?:\'s|s)?\b|\bm\.?(?:s|a|b\.?a)\b",                  "master"),
    (r"\bbachelor(?:\'s|s)?\b|\bb\.?(?:s|a)\b|\bundergraduate\b",     "bachelor"),
    (r"\bassociate(?:\'s|s)?\b|\ba\.?(?:s|a)\b",                      "associate"),
    (r"\bhigh\s+school\b|\bh\.?s\.?\b|\bg\.?e\.?d\b",                "high_school"),
]
_EDU_RE = [(re.compile(pat, re.I), level) for pat, level in _EDU_PATTERNS]

_EDU_ORDER = ["doctorate", "master", "bachelor", "associate", "high_school"]


def extract_education_level(text: str) -> Optional[str]:
    found = set()
    for pattern, level in _EDU_RE:
        if pattern.search(text):
            found.add(level)
    if not found:
        return None
    return min(found, key=_EDU_ORDER.index)  # return highest requirement found


# ── Certification extraction ───────────────────────────────────────────────────

_CERT_PATTERN = re.compile(
    r"\b(CPA|CFA|PMP|MBA|RN|LPN|MD|JD|PE|LCSW|LMSW|SHRM-CP|SHRM-SCP"
    r"|CTS|CISSP|CISM|CISA|AWS|GCP|AZURE|COMPTIA|A\+|NETWORK\+|SECURITY\+"
    r"|CCNA|CCNP|CCIE|PMP|CAPM|ITIL|MCSE|MCSA|RHCE|RHCSA|PHR|SPHR"
    r"|CRC|CPHT|EMT|AEMT|NREMT|CPR|AED|OSHA|CDL|FAA|FINRA|SERIES\s*\d+)\b",
    re.I,
)


def extract_certifications(text: str) -> list[str]:
    return sorted({m.group().upper() for m in _CERT_PATTERN.finditer(text)})


# ── Language extraction ────────────────────────────────────────────────────────

_LANG_PATTERN = re.compile(
    r"\b(Spanish|Mandarin|Cantonese|Chinese|French|Russian|Arabic|Korean"
    r"|Portuguese|Italian|Polish|Bengali|Haitian Creole|Creole|Yiddish"
    r"|Japanese|Hindi|Urdu|Vietnamese|Tagalog|Greek|Hebrew)\b",
    re.I,
)


def extract_languages(text: str) -> list[str]:
    return sorted({m.group().title() for m in _LANG_PATTERN.finditer(text)})


# ── Experience years extraction ────────────────────────────────────────────────

_EXP_PATTERN = re.compile(
    r"(\d+)\+?\s*(?:or more\s*)?years?(?:\s+of)?\s+(?:related\s+|relevant\s+|professional\s+|work\s+)?experience",
    re.I,
)


def extract_experience_years(text: str) -> Optional[int]:
    matches = [int(m.group(1)) for m in _EXP_PATTERN.finditer(text)]
    return min(matches) if matches else None


# ── Date parsing ───────────────────────────────────────────────────────────────

def parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:26], fmt).date()
        except ValueError:
            continue
    return None


# ── Schema mappers ─────────────────────────────────────────────────────────────

def _description_for_public(r: dict) -> str:
    parts = [
        r.get("job_description", ""),
        r.get("minimum_qual_requirements", ""),
        r.get("preferred_skills", ""),
        r.get("additional_information", ""),
    ]
    return "\n".join(p for p in parts if p)


def map_public(r: dict, skills: list[str], skill_ids: list[str]) -> dict:
    desc = _description_for_public(r)
    sal_from = float(r["salary_range_from"]) if r.get("salary_range_from") else None
    sal_to   = float(r["salary_range_to"])   if r.get("salary_range_to")   else None
    period   = normalize_period(r.get("salary_frequency"))
    ind = r.get("full_time_part_time_indicator", "")
    emp_type = "full_time" if ind == "F" else "part_time" if ind == "P" else None
    work_loc = r.get("work_location", "")

    return {
        "id":                 r["job_id"],
        "sector":             "public",
        "title":              r.get("business_title"),
        "employer":           r.get("agency"),
        "industry":           r.get("job_category"),
        "borough":            detect_borough(work_loc) or detect_borough(desc),
        "work_address":       work_loc or None,
        "workplace_type":     "on_site",
        "employment_type":    emp_type,
        "career_level":       r.get("career_level"),
        "salary_min":         sal_from,
        "salary_max":         sal_to,
        "salary_min_annual":  to_annual(sal_from, period),
        "salary_max_annual":  to_annual(sal_to, period),
        "salary_period":      period,
        "skills":             skills,
        "skill_ids":          skill_ids,
        "education_level":    extract_education_level(desc),
        "certifications":     extract_certifications(desc),
        "languages_required": extract_languages(desc),
        "experience_years_min": extract_experience_years(desc),
        "posting_date":       parse_date(r.get("posting_date")),
        "expiry_date":        parse_date(r.get("post_until")),
        "posting_type":       r.get("posting_type", "").lower() or None,
        "number_of_positions": int(r["number_of_positions"]) if r.get("number_of_positions") else None,
        "apply_url":          r.get("to_apply"),
        "source_url":         None,
        "description":        desc,
    }


def map_private(r: dict, skills: list[str], skill_ids: list[str]) -> dict:
    desc    = r.get("description_text", "")
    sal_min = r.get("salary_min")
    sal_max = r.get("salary_max")
    period  = normalize_period(r.get("salary_period"))

    # Best-effort employer name: try first non-empty line of description
    employer = None
    for line in desc.splitlines():
        line = line.strip()
        if line and len(line) < 80 and not line.startswith(("http", "•", "-")):
            employer = line
            break

    raw_wt = r.get("workplace_type") or r.get("remote_policy")
    if raw_wt:
        wt = raw_wt.lower()
        workplace_type = "remote" if "remote" in wt else "hybrid" if "hybrid" in wt else "on_site"
    else:
        workplace_type = None

    loc_text = r.get("location_text", "")

    return {
        "id":                 r["job_id"],
        "sector":             "private",
        "title":              r.get("title"),
        "employer":           employer,
        "industry":           r.get("department"),
        "borough":            detect_borough(loc_text) or detect_borough(desc),
        "work_address":       None,
        "workplace_type":     workplace_type,
        "employment_type":    normalize_employment_type(r.get("employment_type")),
        "career_level":       None,
        "salary_min":         sal_min,
        "salary_max":         sal_max,
        "salary_min_annual":  to_annual(sal_min, period),
        "salary_max_annual":  to_annual(sal_max, period),
        "salary_period":      period,
        "skills":             skills,
        "skill_ids":          skill_ids,
        "education_level":    extract_education_level(desc),
        "certifications":     extract_certifications(desc),
        "languages_required": extract_languages(desc),
        "experience_years_min": extract_experience_years(desc),
        "posting_date":       parse_date(r.get("source_posted_at")),
        "expiry_date":        None,
        "posting_type":       None,
        "number_of_positions": None,
        "apply_url":          r.get("apply_url"),
        "source_url":         r.get("source_url"),
        "description":        desc,
    }


# ── Skills extraction ──────────────────────────────────────────────────────────

def extract_skills_batch(
    descriptions: list[str],
    extractor,
) -> list[tuple[list[str], list[str]]]:
    results = extractor(descriptions)
    output = []
    for doc in results:
        mapped = doc._.mapped_skills or []
        names = [s["skill_label"] for s in mapped if s.get("skill_label")]
        ids   = [str(s["skill_id"])    for s in mapped if s.get("skill_id")]
        output.append((names, ids))
    return output


# ── Checkpoint helpers ─────────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {}


def save_checkpoint(data: dict) -> None:
    with open(CHECKPOINT, "w") as f:
        json.dump(data, f)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading raw data...")
    with open(PUBLIC_RAW)  as f: public_records  = json.load(f)
    with open(PRIVATE_RAW) as f: private_records = json.load(f)

    all_records = [("public",  r) for r in public_records] + \
                  [("private", r) for r in private_records]
    total = len(all_records)
    print(f"  {len(public_records)} public + {len(private_records)} private = {total} total records")

    print(f"\nLoading skills extractor (taxonomy={TAXONOMY})...")
    from ojd_daps_skills.extract_skills.extract_skills import SkillsExtractor
    extractor = SkillsExtractor(taxonomy_name=TAXONOMY)

    checkpoint = load_checkpoint()
    print(f"  Checkpoint loaded: {len(checkpoint)} records already processed")

    # Identify which records still need skill extraction
    pending = [(sector, r) for sector, r in all_records
               if r["job_id"] not in checkpoint]
    print(f"  {len(pending)} records need skill extraction")

    # Extract skills in batches
    descriptions = []
    batch_meta   = []  # (job_id,) per item
    processed_since_checkpoint = 0

    def flush_batch():
        nonlocal processed_since_checkpoint
        if not descriptions:
            return
        results = extract_skills_batch(descriptions, extractor)
        for (job_id,), (names, ids) in zip(batch_meta, results):
            checkpoint[job_id] = {"skills": names, "skill_ids": ids}
        processed_since_checkpoint += len(descriptions)
        descriptions.clear()
        batch_meta.clear()

    for i, (sector, r) in enumerate(pending):
        if sector == "public":
            desc = _description_for_public(r)
        else:
            desc = r.get("description_text", "")

        descriptions.append(desc)
        batch_meta.append((r["job_id"],))

        if len(descriptions) >= SKILL_BATCH_SIZE:
            flush_batch()
            done = len(checkpoint)
            print(f"  Skills: {done} / {total} processed...")

        if processed_since_checkpoint >= CHECKPOINT_EVERY:
            save_checkpoint(checkpoint)
            processed_since_checkpoint = 0
            print(f"  Checkpoint saved ({len(checkpoint)} records)")

    flush_batch()  # final partial batch
    save_checkpoint(checkpoint)
    print(f"  Skills extraction complete. Checkpoint saved.")

    # Build unified records
    print("\nBuilding unified schema...")
    rows = []
    for sector, r in all_records:
        job_id = r["job_id"]
        skill_data = checkpoint.get(job_id, {})
        skills    = skill_data.get("skills",    [])
        skill_ids = skill_data.get("skill_ids", [])
        if sector == "public":
            rows.append(map_public(r, skills, skill_ids))
        else:
            rows.append(map_private(r, skills, skill_ids))

    # Write Parquet
    print(f"Writing {OUTPUT_FILE}...")
    df = pd.DataFrame(rows)
    # Parquet requires list columns to have consistent types
    for col in ("skills", "skill_ids", "certifications", "languages_required"):
        df[col] = df[col].apply(lambda x: x if isinstance(x, list) else [])
    df.to_parquet(OUTPUT_FILE, index=False, engine="pyarrow")

    size_mb = os.path.getsize(OUTPUT_FILE) / 1_048_576
    print(f"  Saved {OUTPUT_FILE} ({len(df)} rows, {size_mb:.1f} MB)")

    os.remove(CHECKPOINT)
    print("  Checkpoint removed.")
    print("\nDone.")


if __name__ == "__main__":
    main()

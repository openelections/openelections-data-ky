#!/usr/bin/env python3
"""
Parse KY 2026 primary county precinct PDFs into individual CSV files.

Source: openelections-sources-ky/2026/primary/<County>.pdf
Output: openelections-data-ky/2026/counties/20260519__ky__primary__{county}__precinct.csv

The parser handles the "Adair format": each page lists one precinct followed by
one or more contests.  For every contest it emits rows for each candidate plus
pseudo-candidate rows for Total Votes, Under Votes and Over Votes.  Cast Votes
rows are skipped.

Vote breakdown columns are taken from the PDF columns:
    Absentee Mail-In -> absentee_mail
    Absentee Walk-In -> absentee
    Early Voting     -> early_voting
    Election Day     -> election_day
    Total            -> votes

Usage:
    uv run python3 parse_2026_primary_precincts.py
"""

import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import natural_pdf

ELECTION_DATE = "20260519"
SOURCE_DIR = Path("/Users/dwillis/code/openelections-sources-ky/2026/primary")
OUTPUT_DIR = Path("/Users/dwillis/code/openelections-data-ky/2026/counties")
COUNTY_CSV = Path("/Users/dwillis/code/openelections-data-ky/2026/20260519__ky__primary__county.csv")

COUNTIES = {
    "Adair", "Allen", "Anderson", "Ballard", "Barren", "Bath", "Bell", "Boone",
    "Bourbon", "Boyd", "Boyle", "Bracken", "Breathitt", "Breckinridge", "Bullitt",
    "Butler", "Caldwell", "Calloway", "Campbell", "Carlisle", "Carroll", "Carter",
    "Casey", "Christian", "Clark", "Clay", "Clinton", "Crittenden", "Cumberland",
    "Daviess", "Edmonson", "Elliott", "Estill", "Fayette", "Fleming", "Floyd",
    "Franklin", "Fulton", "Gallatin", "Garrard", "Grant", "Graves", "Grayson",
    "Green", "Greenup", "Hancock", "Hardin", "Harlan", "Harrison", "Hart",
    "Henderson", "Henry", "Hickman", "Hopkins", "Jackson", "Jefferson",
    "Jessamine", "Johnson", "Kenton", "Knott", "Knox", "Larue", "Laurel",
    "Lawrence", "Lee", "Leslie", "Letcher", "Lewis", "Lincoln", "Livingston",
    "Logan", "Lyon", "Madison", "Magoffin", "Marion", "Marshall", "Martin",
    "Mason", "McCracken", "McCreary", "McLean", "Meade", "Menifee", "Mercer",
    "Metcalfe", "Monroe", "Montgomery", "Morgan", "Muhlenberg", "Nelson",
    "Nicholas", "Ohio", "Oldham", "Owen", "Owsley", "Pendleton", "Perry",
    "Pike", "Powell", "Pulaski", "Robertson", "Rockcastle", "Rowan", "Russell",
    "Scott", "Shelby", "Simpson", "Spencer", "Taylor", "Todd", "Trigg",
    "Trimble", "Union", "Warren", "Washington", "Wayne", "Webster", "Whitley",
    "Wolfe", "Woodford",
}

# Headers that identify the Adair-style table format.
# Most counties include an "Early Voting" column; Bracken omits it.
FORMAT_HEADERS = (
    (
        "Choice Party Absentee Mail-In Absentee Walk-In Early Voting "
        "Election Day Voting Total"
    ),
    (
        "Choice Party Absentee Mail-In Absentee Walk-In "
        "Election Day Voting Total"
    ),
)
FORMAT_HEADER_RE = re.compile(
    r"Choice\s+Party\s+Absentee\s+Mail-?\s*[Ii]n\s+Absentee\s+Walk-?\s*[Ii]n\s+"
    r"(?:Early\s+Voting\s+)?Election\s+Day\s+Voting\s+Total",
    re.IGNORECASE,
)


OFFICE_REPLACEMENTS = {
    "UNITED STATES REPRESENTATIVE IN CONGRESS": "U.S. House",
    "UNITED STATES SENATOR": "U.S. Senate",
    "U.S. SENATOR": "U.S. Senate",
    "U.S. REPRESENTATIVE": "U.S. House",
    "COUNTY JUDGE/EXECUTIVE": "County Judge/Executive",
    "COUNTY CLERK": "County Clerk",
    "SHERIFF": "Sheriff",
    "JAILER": "Jailer",
    "CORONER": "Coroner",
    "COUNTY ATTORNEY": "County Attorney",
    "COUNTY SURVEYOR": "County Surveyor",
    "MAGISTRATE": "Magistrate",
    "CONSTABLE": "Constable",
    "STATE REPRESENTATIVE": "State Representative",
    "STATE SENATOR": "State Senate",
}


def title_case_office(office):
    """Convert an office string to title case while preserving known acronyms."""
    upper = office.upper()
    for old, new in OFFICE_REPLACEMENTS.items():
        if upper == old or upper.startswith(old + " "):
            # Preserve remainder (e.g. district info) for later extraction.
            remainder = office[len(old):].strip()
            return new, remainder

    # Generic title-casing.
    parts = []
    for word in office.split():
        if word.upper() in {"U.S.", "US", "IN", "FOR", "OF", "THE", "AND"}:
            parts.append(word.upper() if word.upper() != "AND" else "and")
        else:
            parts.append(word.capitalize())
    return " ".join(parts), ""


DISTRICT_RE = re.compile(
    r"(?:(\d+)(?:st|nd|rd|th)\s+Congressional\s+District)|"
    r"(?:(\d+)(?:st|nd|rd|th)\s+Representative\s+District)|"
    r"(?:(\d+)(?:st|nd|rd|th)\s+Senatorial\s+District)|"
    r"(?:District\s+(\d+))|"
    r"(?:State\s+Representative\s+(\d+))|"
    r"(?:State\s+Senator\s+(\d+))|"
    r"(?:\b(\d+)\b)"
)

# Ballot questions / constitutional amendments appear as contests with
# YES/NO (or FOR/AGAINST) "candidates".  They are not tracked in the
# county-level totals, so we skip them entirely.
QUESTION_RE = re.compile(
    r"^(?:QUESTION|CONSTITUTIONAL\s+AMENDMENT|LOCAL\s+OPTION|"
    r"REFERENDUM|BALLOT\s+QUESTION|PROPOSED\s+(?:AMENDMENT|CONSTITUTION)|"
    r"Shall\s)",
    re.IGNORECASE,
)


def _ordinal(n):
    """Return the English ordinal suffix for an integer."""
    n = int(n)
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


JUDGE_RE = re.compile(
    r"District\s+Judge\s+(\d+)(?:st|nd|rd|th)\s+Judicial\s+District\s+(\d+)(?:st|nd|rd|th)\s+(?:Division|District)",
    re.IGNORECASE,
)


def extract_office_district(title):
    """Return (office, district) from a contest title line."""
    # Strip the "- (Vote for One)" suffix.
    title = re.sub(r"\s*-\s*\(Vote for .*?\)\s*$", "", title).strip()

    # Canonicalize District Judge races to match the county-level totals format.
    m = JUDGE_RE.search(title)
    if m:
        office = f"District Judge, {_ordinal(m.group(1))} Judicial District"
        return office, m.group(2)

    office, remainder = title_case_office(title)
    district = ""

    # Try to pull a district number from the remainder first.
    if remainder:
        m = DISTRICT_RE.search(remainder)
        if m:
            district = next(g for g in m.groups() if g is not None)

    # If nothing in the remainder, search the whole title.
    if not district:
        m = DISTRICT_RE.search(title)
        if m:
            district = next(g for g in m.groups() if g is not None)

    return office, district


def parse_candidate_line(line, num_columns):
    """
    Parse a candidate row.

    Returns dict with keys: candidate, absentee_mail, absentee, early_voting,
    election_day, votes.  `num_columns` is 4 (Bracken) or 5 (Adair style).

    Five-column Adair line:
        Other Donald WENZEL 0 0.00% 0 0.00% 0 0.00% 0 0.00% 0 0.00%
    Four-column Bracken line:
        A. Nick SHELLEY 0 0.00% 2 4.55% 3 2.36% 5 2.89%
    """
    tokens = line.split()
    counts = []
    pct_seen = 0
    i = len(tokens) - 1
    while i >= 0 and pct_seen < num_columns:
        tok = tokens[i]
        if tok.endswith("%"):
            # The token before the percentage is the count.
            if i - 1 < 0:
                raise ValueError(f"Malformed candidate line: {line!r}")
            count = tokens[i - 1].replace(",", "")
            counts.append(count)
            i -= 2
            pct_seen += 1
        else:
            # Some PDFs omit percentages; treat bare numbers as counts.
            # This fallback should not be needed for the Adair format.
            counts.append(tok.replace(",", ""))
            i -= 1
            pct_seen += 1

    if pct_seen != num_columns:
        raise ValueError(
            f"Could not find {num_columns} count/percentage pairs in: {line!r}"
        )

    counts.reverse()
    if num_columns == 5:
        absentee_mail, absentee, early_voting, election_day, votes = counts
    elif num_columns == 4:
        absentee_mail, absentee, election_day, votes = counts
        early_voting = ""
    else:
        raise ValueError(f"Unsupported column count: {num_columns}")

    name = " ".join(tokens[:i + 1]).strip()

    return {
        "candidate": name,
        "absentee_mail": absentee_mail,
        "absentee": absentee,
        "early_voting": early_voting,
        "election_day": election_day,
        "votes": votes,
    }


def parse_under_over_line(line, num_columns):
    """
    Parse Undervotes:/Overvotes: lines.

    They contain only counts, no percentages:
        Five columns:  Undervotes: 2 0 7 8 17
        Four columns:  Undervotes: 0 1 9 10
    """
    label, rest = line.split(":", 1)
    counts = rest.split()
    if len(counts) != num_columns:
        raise ValueError(
            f"Expected {num_columns} counts in under/over line: {line!r}"
        )

    counts = [c.replace(",", "") for c in counts]
    if num_columns == 5:
        absentee_mail, absentee, early_voting, election_day, votes = counts
    elif num_columns == 4:
        absentee_mail, absentee, election_day, votes = counts
        early_voting = ""
    else:
        raise ValueError(f"Unsupported column count: {num_columns}")

    return {
        "absentee_mail": absentee_mail,
        "absentee": absentee,
        "early_voting": early_voting,
        "election_day": election_day,
        "votes": votes,
    }


def looks_like_format_header(line):
    return bool(FORMAT_HEADER_RE.search(line))


def detect_format_columns(text):
    """
    Determine whether the page uses 4-column (Bracken) or 5-column (Adair)
    format by inspecting the first format header line.
    """
    for ln in text.splitlines():
        if looks_like_format_header(ln):
            return 4 if "Early" not in ln else 5
    return 5


def parse_page(text, county):
    """Parse a single page of text. Returns (precinct, ballots_cast, rows)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    num_columns = detect_format_columns(text)

    # Find the precinct line, e.g. "A102 179 ballots cast"
    precinct = None
    ballots_cast = None
    for ln in lines:
        # Standard Adair format: "A102 179 ballots cast" or "A109-DOUGLAS-WASHINGTON 190 ballots cast"
        m = re.match(r"^([A-Z]\d{1,4}[A-Z]?)\s*(?:-\s*([A-Z][A-Z\s\.\-]+))?\s+([\d,]+)\s+ballots?\s+cast", ln, re.IGNORECASE)
        # Pike-style format: "A101 166 of 0 registered voters = 0.00%"
        if not m:
            m = re.match(r"^([A-Z]\d{1,4}[A-Z]?)\s*(?:-\s*([A-Z][A-Z\s\.\-]+))?\s+([\d,]+)\s+of\s+[\d,]+\s+registered\s+voters", ln, re.IGNORECASE)
        if m:
            precinct = m.group(1).strip()
            ballots_cast = m.group(3).replace(",", "")
            break

    if not precinct:
        return None, None, []

    rows = []
    current_office = None
    current_district = None

    for ln in lines:
        if looks_like_format_header(ln):
            # Re-detect column count if the header line itself changed.
            num_columns = 4 if "Early" not in ln else 5
            continue
        if "Cast Votes:" in ln:
            continue
        if "- (Vote for" in ln or QUESTION_RE.search(ln):
            if QUESTION_RE.search(ln):
                current_office = None
                current_district = None
            else:
                current_office, current_district = extract_office_district(ln)
            continue
        if not current_office:
            continue
        if "Undervotes:" in ln:
            data = parse_under_over_line(ln, num_columns)
            rows.append({
                "county": county,
                "precinct": precinct,
                "office": current_office,
                "district": current_district,
                "party": "",
                "candidate": "Under Votes",
                **data,
            })
            continue
        if "Overvotes:" in ln:
            data = parse_under_over_line(ln, num_columns)
            rows.append({
                "county": county,
                "precinct": precinct,
                "office": current_office,
                "district": current_district,
                "party": "",
                "candidate": "Over Votes",
                **data,
            })
            continue
        if not current_office:
            continue
        # Candidate or Total Votes row.  Require at least one percentage token.
        if "%" not in ln:
            continue
        try:
            data = parse_candidate_line(ln, num_columns)
        except ValueError:
            continue
        if data["candidate"] in {"YES", "NO", "FOR", "AGAINST"}:
            continue
        rows.append({
            "county": county,
            "precinct": precinct,
            "office": current_office,
            "district": current_district,
            "party": "",
            "candidate": data["candidate"],
            **{k: data[k] for k in ("votes", "early_voting", "election_day", "absentee_mail", "absentee")},
        })

    # Ballots Cast pseudo-office row: only the votes column is populated.
    if ballots_cast:
        rows.append({
            "county": county,
            "precinct": precinct,
            "office": "Ballots Cast",
            "district": "",
            "party": "",
            "candidate": "",
            "votes": ballots_cast,
            "early_voting": "",
            "election_day": "",
            "absentee_mail": "",
            "absentee": "",
        })

    return precinct, ballots_cast, rows


def has_format_header(pdf):
    """Check whether the first data page looks like the Adair format."""
    for page in pdf.pages[:2]:
        text = page.extract_text() or ""
        if FORMAT_HEADER_RE.search(text):
            return True
    return False


def is_image_pdf(pdf):
    """Heuristic: if the first few pages have essentially no text, treat as image PDF."""
    for page in pdf.pages[:3]:
        text = (page.extract_text() or "").strip()
        if len(text) > 200:
            return False
    return True


def parse_county_pdf(pdf_path, county):
    pdf = natural_pdf.PDF(str(pdf_path))

    if is_image_pdf(pdf):
        raise ValueError("No extractable text; appears to be an image PDF")

    if not has_format_header(pdf):
        raise ValueError("Does not match the expected Adair-style format header")

    all_rows = []
    ballots_cast_added = set()
    for page in pdf.pages:
        text = page.extract_text() or ""
        precinct, _, rows = parse_page(text, county)
        # Only emit one Ballots Cast row per precinct across all pages.
        filtered_rows = []
        for row in rows:
            if row["office"] == "Ballots Cast":
                if precinct in ballots_cast_added:
                    continue
                ballots_cast_added.add(precinct)
            filtered_rows.append(row)
        all_rows.extend(filtered_rows)

    # Contests that span multiple pages can produce duplicate Under/Over Vote
    # rows.  Merge them by summing their numeric columns.
    merged = []
    under_over_keys = {}
    for row in all_rows:
        if row["candidate"] in {"Under Votes", "Over Votes"}:
            key = (row["precinct"], row["office"], row["district"], row["candidate"])
            if key in under_over_keys:
                existing = under_over_keys[key]
                for col in ("votes", "early_voting", "election_day", "absentee_mail", "absentee"):
                    a = existing.get(col, "") or "0"
                    b = row.get(col, "") or "0"
                    existing[col] = str(int(a) + int(b))
            else:
                under_over_keys[key] = row
                merged.append(row)
        else:
            merged.append(row)

    return merged


def load_party_lookup(county_csv: Path):
    """Build a lookup of party by (county, office, district, candidate)."""
    lookup = {}
    if not county_csv.exists():
        return lookup

    with open(county_csv, newline="") as f:
        for row in csv.DictReader(f):
            county = row.get("county", "").strip()
            office = row.get("office", "").strip()
            district = row.get("district", "").strip()
            candidate = row.get("candidate", "").strip()
            party = row.get("party", "").strip()
            if not (county and office and candidate):
                continue
            lookup[(county, office, district, candidate)] = party

    return lookup


def _county_name_from_filename(stem: str) -> str:
    """Convert a lowercase filename county slug to the canonical county name."""
    slug = stem.split("__")[3].replace("_", " ").lower()
    for county in COUNTIES:
        if county.lower() == slug:
            return county
    # Fallback title-case for any unexpected filename.
    return " ".join(p.capitalize() for p in slug.split())


def reconcile_with_county_totals(county_csv: Path, party_lookup: dict):
    """
    For each county whose precinct totals fall short of the certification totals,
    append an `Absentee` pseudo-precinct row that makes the county-wide candidate
    totals match.  This mirrors the historical Kentucky convention of reporting
    ballots that are not allocated to a specific precinct (e.g. late absentee or
    provisional votes) in an aggregate Absentee precinct.
    """
    # Load certification totals for all counties once.
    county_totals = defaultdict(int)
    with open(county_csv, newline="") as f:
        for row in csv.DictReader(f):
            key = (
                row.get("county", "").strip(),
                row.get("office", "").strip(),
                row.get("district", "").strip(),
                row.get("candidate", "").strip(),
            )
            votes = row.get("votes", "").strip().replace(",", "")
            if not votes:
                continue
            county_totals[key] = int(votes)

    for path in sorted(OUTPUT_DIR.glob("20260519__ky__primary__*__precinct.csv")):
        county_name = _county_name_from_filename(path.stem)
        # Read existing rows and aggregate candidate votes per key.
        precinct_totals = defaultdict(int)
        rows = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
                candidate = row.get("candidate", "").strip()
                if candidate in {"Under Votes", "Over Votes", "Ballots Cast", "Total Votes"}:
                    continue
                votes = row.get("votes", "").strip().replace(",", "")
                if not votes:
                    continue
                key = (
                    county_name,
                    row.get("office", "").strip(),
                    row.get("district", "").strip(),
                    candidate,
                )
                precinct_totals[key] += int(votes)

        # Build absentee rows for any shortfall.
        absentee_rows = []
        for key, expected in county_totals.items():
            county, office, district, candidate = key
            if county != county_name:
                continue
            actual = precinct_totals.get(key, 0)
            if expected > actual:
                party = party_lookup.get(key, "")
                absentee_rows.append({
                    "county": county,
                    "precinct": "Absentee",
                    "office": office,
                    "district": district,
                    "party": party,
                    "candidate": candidate,
                    "votes": str(expected - actual),
                    "early_voting": "",
                    "election_day": "",
                    "absentee_mail": "",
                    "absentee": "",
                })

        if absentee_rows:
            with open(path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                for row in absentee_rows:
                    writer.writerow(row)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    party_lookup = load_party_lookup(COUNTY_CSV)

    skipped = []
    written = []

    for pdf_path in sorted(SOURCE_DIR.glob("*.pdf")):
        # Skip the statewide certification PDF.
        if "Certification" in pdf_path.stem:
            continue

        county = pdf_path.stem
        if county not in COUNTIES:
            # Allow case-insensitive match (e.g. "LaRue" vs "Larue").
            county_lookup = {c.lower(): c for c in COUNTIES}
            if county.lower() in county_lookup:
                county = county_lookup[county.lower()]
            else:
                skipped.append((pdf_path.stem, "county name not in known list"))
                continue

        try:
            rows = parse_county_pdf(pdf_path, county)
        except Exception as exc:
            skipped.append((county, str(exc)))
            continue

        if not rows:
            skipped.append((county, "no rows parsed"))
            continue

        out_path = OUTPUT_DIR / f"{ELECTION_DATE}__ky__primary__{county.lower()}__precinct.csv"
        fieldnames = [
            "county", "precinct", "office", "district", "party", "candidate",
            "votes", "early_voting", "election_day", "absentee_mail", "absentee",
        ]
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                if not row.get("party"):
                    key = (row["county"], row["office"], row["district"], row["candidate"])
                    row["party"] = party_lookup.get(key, "")
                writer.writerow(row)

        written.append((county, len(rows), out_path))

    # After the base precinct files are written, reconcile any county-wide
    # shortfalls against the certification totals.
    reconcile_with_county_totals(COUNTY_CSV, party_lookup)

    print(f"Wrote {len(written)} county files:")
    for county, n, path in written:
        # Report the base row count; reconcile may have appended Absentee rows.
        print(f"  {county}: {n} rows -> {path}")

    if skipped:
        print(f"\nSkipped {len(skipped)} counties:")
        for county, reason in skipped:
            print(f"  {county}: {reason}")


if __name__ == "__main__":
    main()

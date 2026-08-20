#!/usr/bin/env python3
"""Parse Jefferson County 2026 primary precinct results.

Jefferson uses a six-column Electionware layout:
    TOTAL  Absentee(Mail)  Early Excused(6 Day)  Early Excuse(3 Day)  Provisional  Election Day

We map these to the canonical precinct CSV as:
    votes, early_voting (sum of the two early columns), election_day,
    absentee_mail, absentee (blank), provisional.
"""

import csv
import re
import sys
from pathlib import Path

from natural_pdf import PDF

SOURCE_DIR = Path("/Users/dwillis/code/openelections-sources-ky/2026/primary")
OUT_DIR = Path("/Users/dwillis/code/openelections-data-ky/2026/counties")
COUNTY_CSV = Path("/Users/dwillis/code/openelections-data-ky/2026/20260519__ky__primary__county.csv")

PARTY_MAP = {"REP": "Republican", "DEM": "Democratic"}

PRECINCT_RE = re.compile(r"^([A-Z]\d{1,4}[A-Z]?)\s*(.*)$")
OFFICE_RE = re.compile(r"^(REP|DEM)\s+(.+)$", re.IGNORECASE)


def _name_key(name: str) -> str:
    """Strip suffixes and punctuation for fuzzy name matching."""
    name = name.lower()
    name = re.sub(r"\s*\(withdrawn\)", "", name)
    name = re.sub(r"\s*sr\.?$", "", name)
    name = re.sub(r"\s*jr\.?$", "", name)
    name = re.sub(r"[^a-z]", "", name)
    return name


def load_county_lookup(county_csv: Path):
    """Build a lookup of district/party/canonical name by (county, office, candidate)."""
    lookup = {}
    if not county_csv.exists():
        return lookup
    with open(county_csv, newline="") as f:
        for row in csv.DictReader(f):
            county = row.get("county", "").strip()
            office = row.get("office", "").strip()
            candidate = row.get("candidate", "").strip()
            district = row.get("district", "").strip()
            party = row.get("party", "").strip()
            if county and office and candidate:
                lookup[(county, office, candidate)] = {
                    "district": district,
                    "party": party,
                    "candidate": candidate,
                }
                fuzzy_key = (county, office, _name_key(candidate))
                if fuzzy_key not in lookup:
                    lookup[fuzzy_key] = {
                        "district": district,
                        "party": party,
                        "candidate": candidate,
                    }
    return lookup


def extract_district(raw_office: str) -> str:
    """Pull a district number from the office text when present."""
    m = re.search(
        r"(\d+)(?:st|nd|rd|th)?\s+(?:Congressional|Representative|Senatorial|District|Dist)?\s*District",
        raw_office,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    m = re.search(r"(?:District|Dist)\s*(\d+)", raw_office, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def normalize_office(raw_office: str) -> str:
    """Canonicalize federal/state office names and tidy local office names."""
    if re.search(r"U\.?S\.?\s+Senator", raw_office, re.IGNORECASE):
        return "U.S. Senate"
    if re.search(r"U\.?S\.?\s+Representative", raw_office, re.IGNORECASE):
        return "U.S. House"
    if re.search(r"State\s+Senate", raw_office, re.IGNORECASE):
        return "State Senate"
    if re.search(r"State\s+Representative", raw_office, re.IGNORECASE):
        return "State Representative"

    cleaned = raw_office.title()
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    cleaned = re.sub(
        r"\s*,?\s*\d+(?:st|nd|rd|th)?\s*(?:District|Dist)\.?$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def _coalesce_quoted_nicknames(words: list[str]) -> list[str]:
    """Merge quoted nickname tokens that were split by whitespace."""
    out: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if w.startswith('"'):
            parts = [w]
            j = i
            while not parts[-1].endswith('"') and j + 1 < len(words):
                j += 1
                parts.append(words[j])
            quoted = " ".join(parts)
            inner = quoted[1:-1].replace(".", "").strip()
            out.append(f'"{inner.title()}"')
            i = j + 1
        else:
            out.append(w)
            i += 1
    return out


SUFFIX_RE = re.compile(
    r"(\s*(?:SR\.?|JR\.?|I{2,3}|IV|V|\(Withdrawn\)))$", re.IGNORECASE
)


def normalize_candidate(name: str) -> str:
    """Normalize candidate name: coalesce split nicknames, strip suffixes.

    Source PDFs already provide the desired mixed casing for most names; we
    preserve it and rely on the county-totals lookup for canonical spelling.
    """
    if name in {"Under Votes", "Over Votes", "YES", "NO"}:
        return name

    suffix_match = SUFFIX_RE.search(name)
    suffix = ""
    if suffix_match:
        suffix = suffix_match.group(1)
        name = name[: suffix_match.start()]

    words = _coalesce_quoted_nicknames(name.split())
    if not words:
        return name + suffix

    # Source casing is usually correct; only force the last token to caps if
    # it is a single lowercase token.
    last = words[-1]
    if last.isalpha() and last.islower():
        last = last.upper()
    out = words[:-1] + [last]
    return " ".join(out) + suffix


def looks_like_skip_line(line: str) -> bool:
    """True for lines that are not candidate rows."""
    stripped = line.strip()
    if not stripped:
        return True
    prefixes = (
        "Total Votes Cast",
        "Contest Totals",
        "Vote For",
        "Statistics TOTAL",
        "Registered Voters",
        "Ballots Cast",
        "Voter Turnout",
        "Precinct Summary -",
        "Report generated with Electionware",
        "Summary Results Report",
        "2026 Primary",
        "May 19, 2026",
        "OFFICIAL RESULTS",
        "TOTAL Absentee",
        "(Mail)",
        "(6 Day)",
        "Excused",
        "Excuse",
        "(3 al Day",
        "al Day",
        "Day)",
    )
    return any(stripped.startswith(p) for p in prefixes)


def parse_candidate_line(line: str) -> tuple[str, list[int]] | None:
    """Parse a candidate name plus six trailing integer counts."""
    line = line.rstrip()
    tokens = line.split()
    if not tokens:
        return None
    if len(tokens) >= 7 and all(t.replace(",", "").lstrip("-").isdigit() for t in tokens[-6:]):
        candidate = " ".join(tokens[:-6])
        counts = [int(t.replace(",", "")) for t in tokens[-6:]]
        return candidate.strip(), counts
    return None


def _next_nonblank(lines: list[str], start: int) -> int:
    """Return index of the next non-empty line, or len(lines) if none."""
    i = start
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i


def _next_is_vote_for(lines: list[str], idx: int) -> bool:
    """True if the line at idx is an office line followed by Vote For."""
    if idx >= len(lines):
        return False
    nxt = _next_nonblank(lines, idx + 1)
    return nxt < len(lines) and lines[nxt].strip().startswith("Vote For")


def parse_county(county: str, lookup: dict) -> list[dict]:
    """Extract precinct results from Jefferson County's PDF."""
    pdf_path = SOURCE_DIR / f"{county}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    pdf = PDF(str(pdf_path))
    text = pdf.extract_text()
    lines = text.splitlines()

    rows: list[dict] = []
    current_precinct = ""
    current_office = ""
    current_district = ""
    current_party = ""

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()
        if not line:
            i += 1
            continue

        # Precinct lines are a code like A107, optionally followed by a short name.
        m = PRECINCT_RE.match(line)
        if m and not line.startswith("REP") and not line.startswith("DEM"):
            # Confirm it's a precinct by checking the next nonblank line is an office.
            nxt = _next_nonblank(lines, i + 1)
            if nxt < len(lines) and (
                lines[nxt].strip().startswith(("REP", "DEM"))
                or _next_is_vote_for(lines, nxt)
            ):
                current_precinct = m.group(1)
                i += 1
                continue

        # Office lines may be prefixed by REP/DEM, or (for Louisville races) have no prefix.
        nxt = _next_nonblank(lines, i + 1)
        is_office = nxt < len(lines) and lines[nxt].strip().startswith("Vote For")
        if is_office:
            raw_office = line
            m_off = OFFICE_RE.match(raw_office)
            if m_off:
                party_code = m_off.group(1).upper()
                raw_office = m_off.group(2).strip()
                current_party = PARTY_MAP.get(party_code, party_code)
            else:
                current_party = ""
            current_office = normalize_office(raw_office)
            # In Jefferson the "District" label on U.S. Senate is the state
            # senate district, not a U.S. Senate district; leave it blank.
            current_district = "" if current_office == "U.S. Senate" else extract_district(raw_office)
            i += 1
            continue

        if looks_like_skip_line(line):
            i += 1
            continue

        parsed = parse_candidate_line(line)
        if parsed is None:
            i += 1
            continue

        candidate, counts = parsed
        candidate = normalize_candidate(candidate)

        if not current_precinct or not current_office:
            i += 1
            continue

        total, mail, ev_excused, ev_unexcused, provisional, election_day = counts
        early_voting = ev_excused + ev_unexcused

        # Backfill district/party/canonical candidate spelling from the county totals.
        district = current_district
        party = current_party
        exact_key = (county, current_office, candidate)
        fuzzy_key = (county, current_office, _name_key(candidate))
        if exact_key in lookup:
            info = lookup[exact_key]
        elif fuzzy_key in lookup:
            info = lookup[fuzzy_key]
        else:
            info = None

        if info:
            candidate = info["candidate"]
            if not district:
                district = info["district"]
            if not party:
                party = info["party"]

        rows.append(
            {
                "county": county,
                "precinct": current_precinct,
                "office": current_office,
                "district": district,
                "party": party,
                "candidate": candidate,
                "votes": total,
                "early_voting": early_voting,
                "election_day": election_day,
                "absentee_mail": mail,
                "absentee": "",
                "provisional": provisional,
            }
        )
        i += 1

    return rows


def write_county_csv(county: str, rows: list[dict]) -> Path:
    """Write the parsed rows to the canonical per-county precinct CSV."""
    out_path = OUT_DIR / f"20260519__ky__primary__{county.lower()}__precinct.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "county", "precinct", "office", "district", "party", "candidate",
        "votes", "early_voting", "election_day", "absentee_mail", "absentee", "provisional",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def main():
    lookup = load_county_lookup(COUNTY_CSV)
    rows = parse_county("Jefferson", lookup)
    out_path = write_county_csv("Jefferson", rows)
    print(f"Jefferson: {len(rows):,} rows -> {out_path}")


if __name__ == "__main__":
    main()

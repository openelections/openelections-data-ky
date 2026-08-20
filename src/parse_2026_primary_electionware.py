#!/usr/bin/env python3
"""Parse Kentucky 2026 primary Electionware 'Summary Results Report' PDFs.

Produces per-county precinct CSVs in the OpenElections canonical format:
    county,precinct,office,district,party,candidate,votes,early_voting,election_day,absentee_mail,absentee

Two variants are handled:
    * Detailed: columns are TOTAL, Mail (In), EV (excused), EV (unexcused),
      Election Day.  The two EV columns are summed into early_voting.
    * Totals-only: a single TOTAL column; all breakdown columns are blank.
"""

import csv
import difflib
import re
import sys
import tempfile
from pathlib import Path

from natural_pdf import PDF
from pdf2image import convert_from_path

SOURCE_DIR = Path("/Users/dwillis/code/openelections-sources-ky/2026/primary")
OUT_DIR = Path("/Users/dwillis/code/openelections-data-ky/2026/counties")
COUNTY_CSV = Path("/Users/dwillis/code/openelections-data-ky/2026/20260519__ky__primary__county.csv")

DETAILED_COUNTIES = [
    "Clay", "Clinton", "Jackson", "Knox", "Laurel", "Lee", "Letcher",
    "Madison", "Martin", "Menifee", "Morgan", "Powell", "Rockcastle", "Wolfe",
]
TOTALS_ONLY_COUNTIES = [
    "Breathitt", "Floyd", "Johnson", "Kenton", "Knott", "Magoffin",
]

# Counties whose PDFs are scanned images and must be read with PaddleOCR.
OCR_COUNTIES = ["Elliott", "Leslie"]

PARTY_MAP = {"REP": "Republican", "DEM": "Democratic"}

_OCR = None

PRECINCT_RE = re.compile(r"^([A-Z]\d{1,4}[A-Z]?)\s+(.+)$")
OFFICE_RE = re.compile(r"^(REP|DEM)\s+(.+)$", re.IGNORECASE)
VOTE_FOR_RE = re.compile(r"^Vote\s*For", re.IGNORECASE)


def load_county_lookup(county_csv: Path):
    """Build a lookup of district/party by (county, office, candidate)."""
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
            if county and office and candidate:
                lookup[(county, office, candidate)] = {"district": district, "party": party}
    return lookup


def _get_ocr():
    """Return a lazily initialized PaddleOCR instance."""
    global _OCR
    if _OCR is None:
        from paddleocr import PaddleOCR
        _OCR = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _OCR


OCR_HEADER_TOKENS = {
    "total",
    "mail",
    "ev",
    "election",
    "day",
    "excused",
    "unexcused",
    "in",
    "absentee",
    "walk-in",
    "early",
    "voting",
    "3 day",
    "mail-in",
    "excused 6 unexcused",
    "election day",
}


def _is_numeric_token(token: str) -> bool:
    return token.replace(",", "").lstrip("-").isdigit()


def preprocess_ocr_text(text: str) -> str:
    """Merge OCR text boxes that belong to the same candidate row.

    PaddleOCR returns each table cell as a separate line.  A candidate name
    line is followed by one or more numeric vote lines; rejoin them so the
    existing candidate-line parser can handle them.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.lower() in OCR_HEADER_TOKENS:
            i += 1
            continue
        if looks_like_skip_line(line):
            out.append(line)
            i += 1
            continue
        # Drop isolated OCR noise such as a misread "0" rendered as "D".
        if re.fullmatch(r"[A-Z]", line):
            i += 1
            continue

        # Candidate/precinct/office lines are non-numeric.  Try to consume
        # trailing numeric vote counts.
        if not _is_numeric_token(line):
            j = i + 1
            nums: list[str] = []
            while j < len(lines) and _is_numeric_token(lines[j].strip()):
                nums.append(lines[j].strip())
                j += 1
            if nums:
                out.append(line + " " + " ".join(nums))
                i = j
                continue

        out.append(line)
        i += 1
    return "\n".join(out)


def extract_text_ocr(pdf_path: Path, dpi: int = 200) -> str:
    """Render a scanned PDF to images and return OCR'd text line-by-line."""
    ocr = _get_ocr()
    lines: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        images = convert_from_path(str(pdf_path), dpi=dpi)
        for i, img in enumerate(images, start=1):
            img_path = Path(tmpdir) / f"page_{i:03d}.png"
            img.save(img_path)
            result = ocr.ocr(str(img_path))
            rec_texts = result[0].str["res"]["rec_texts"]
            lines.extend(rec_texts)
    return preprocess_ocr_text("\n".join(lines))


def extract_district(raw_office: str) -> str:
    """Pull a district number from the office text when present."""
    # "4th Congressional District", "91st District", "2nd Representative District"
    m = re.search(
        r"(\d+)(?:st|nd|rd|th)?\s+(?:Congressional|Representative|Senatorial)?\s*District",
        raw_office,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    # "DIST. 1", "Dist 1"
    m = re.search(r"(?:DISTRICT|DIST\.?)\s*(\d+)", raw_office, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""


def normalize_office(raw_office: str) -> str:
    """Canonicalize federal/state office names and tidy local office names."""
    # Allow the occasional "Unites States Senator" OCR/extraction typo.
    if re.search(r"Unite[ds]\s+States\s+Senator", raw_office, re.IGNORECASE):
        return "U.S. Senate"
    if re.search(r"Unite[ds]\s+States\s+Representative", raw_office, re.IGNORECASE):
        return "U.S. House"
    if re.search(r"State\s+Senator", raw_office, re.IGNORECASE):
        return "State Senate"
    # Tolerate the occasional "State Represntative" typo.
    if re.search(r"State\s+Repres(?:en|n)?tative", raw_office, re.IGNORECASE):
        return "State Representative"

    cleaned = raw_office.title()
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    # Remove a trailing district suffix from local offices.
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
    """Apply OpenElections name casing: title-case first/middle, all-caps last."""
    if name in {"Under Votes", "Over Votes", "YES", "NO"}:
        return name

    # Strip and reattach generational/withdrawal suffixes so they do not affect casing.
    suffix_match = SUFFIX_RE.search(name)
    suffix = ""
    if suffix_match:
        suffix = suffix_match.group(1)
        name = name[: suffix_match.start()]

    words = _coalesce_quoted_nicknames(name.split())
    out = []
    for i, w in enumerate(words):
        w = w.title()
        if i == len(words) - 1 and w[0].isalpha():
            lower = w.lower()
            if lower.startswith("mc") and len(w) > 2:
                w = "Mc" + w[2:].upper()
            elif lower.startswith("mac") and len(w) > 3:
                w = "Mac" + w[3:].upper()
            else:
                w = w.upper()
        out.append(w)
    return " ".join(out) + suffix


def _ocr_name_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def fuzzy_match_candidate(
    county: str, office: str, candidate: str, lookup: dict
) -> tuple[str, str, str]:
    """Try to fix OCR candidate names and return (name, district, party)."""
    if candidate in {"Under Votes", "Over Votes", "YES", "NO"}:
        return candidate, "", ""

    choices = [k[2] for k in lookup if k[0] == county and k[1] == office]
    if not choices:
        return candidate, "", ""

    # Exact match after canonicalization.
    if candidate in choices:
        info = lookup[(county, office, candidate)]
        return candidate, info.get("district", ""), info.get("party", "")

    # Exact match after stripping punctuation and case.
    key = _ocr_name_key(candidate)
    choice_keys = [_ocr_name_key(c) for c in choices]
    if key in choice_keys:
        match = choices[choice_keys.index(key)]
        info = lookup[(county, office, match)]
        return match, info.get("district", ""), info.get("party", "")

    # Fuzzy match on the raw name string.
    matches = difflib.get_close_matches(candidate, choices, n=1, cutoff=0.8)
    if matches:
        match = matches[0]
        info = lookup[(county, office, match)]
        return match, info.get("district", ""), info.get("party", "")

    # Fuzzy match on the compacted key (handles dropped leading characters).
    key_matches = difflib.get_close_matches(key, choice_keys, n=1, cutoff=0.85)
    if key_matches:
        match = choices[choice_keys.index(key_matches[0])]
        info = lookup[(county, office, match)]
        return match, info.get("district", ""), info.get("party", "")

    return candidate, "", ""


def deduplicate_ocr_candidates(rows: list[dict]) -> list[dict]:
    """Merge candidate names that are OCR variants of the same person.

    Within each county/office, cluster candidate names whose compacted keys
    are similar and re-aggregate the vote totals under the cleanest name.
    """
    by_office: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        by_office.setdefault((row["county"], row["office"]), []).append(row)

    canonical_map: dict[tuple[str, str, str], str] = {}
    for (county, office), office_rows in by_office.items():
        # Total votes per raw candidate name to prefer the cleanest/most-voted.
        name_votes: dict[str, int] = {}
        for row in office_rows:
            name_votes[row["candidate"]] = name_votes.get(row["candidate"], 0) + int(row["votes"])
        names = sorted(name_votes.keys(), key=lambda n: (-name_votes[n], -len(n)))
        clusters: list[tuple[str, set[str]]] = []
        for name in names:
            key = _ocr_name_key(name)
            match = None
            for can, keys in clusters:
                if key in keys or difflib.SequenceMatcher(None, key, _ocr_name_key(can)).ratio() >= 0.85:
                    match = can
                    keys.add(key)
                    break
            if match:
                canonical_map[(county, office, name)] = match
            else:
                clusters.append((name, {key}))
                canonical_map[(county, office, name)] = name

    # Re-aggregate rows under canonical candidate names.
    groups: dict[tuple, dict] = {}
    breakdown_keys = ["early_voting", "election_day", "absentee_mail", "absentee"]
    for row in rows:
        can = canonical_map[(row["county"], row["office"], row["candidate"])]
        key = (row["county"], row["precinct"], row["office"], row["district"], row["party"], can)
        if key not in groups:
            groups[key] = {
                "county": row["county"],
                "precinct": row["precinct"],
                "office": row["office"],
                "district": row["district"],
                "party": row["party"],
                "candidate": can,
                "votes": 0,
            }
            for bk in breakdown_keys:
                groups[key][bk] = ""
        groups[key]["votes"] += int(row["votes"])
        for bk in breakdown_keys:
            val = row.get(bk, "")
            if val != "":
                cur = groups[key][bk]
                groups[key][bk] = str((int(cur) if cur != "" else 0) + int(val))

    return list(groups.values())


def looks_like_skip_line(line: str) -> bool:
    """True for lines that are not candidate rows."""
    stripped = line.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    # Page headers and report metadata that OCR may emit with trailing numbers.
    if re.search(r"^KY\s+.*\s+County\s+.*Primary", stripped, re.IGNORECASE):
        return True
    if re.search(r"\bprimary election\b", lowered):
        return True
    if re.search(r"\d{1,2}:\d{2}\s*(?:am|pm)\b", lowered):
        return True
    if re.search(r"\b\d+\s*of\s*\d+\b", lowered, re.IGNORECASE):
        return True
    if "county precinct" in lowered:
        return True
    if re.search(r"\bcast\s*-\s*(?:total|republican|democratic|nonpartisan|blank)\b", lowered):
        return True
    if re.search(r"^vote\s*for", lowered):
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
        "Precinct Summary Results Report",
        "Summary Results Report",
        "2026 Primary",
        "May 19, 2026",
        "OFFICIAL RESULTS",
    )
    if any(stripped.startswith(p) for p in prefixes):
        return True
    # OCR can drop initial letters; tolerate common report-only fragments.
    skip_fragments = (
        "allots cast",
        "ballots cast",
        "baflots cast",
        "egistered voters",
        "registered voters",
        "voter turnout",
        "statistics total",
        "votes cast",
        "otal votes cast",
        "tal votes cast",
    )
    return any(fragment in lowered for fragment in skip_fragments)


def parse_candidate_line(line: str) -> tuple[str, list[int]] | None:
    """Parse a candidate name plus trailing integer counts.

    Detailed rows end with five integers: total, mail, ev_excused, ev_unexcused,
    election_day.  Totals-only rows end with one integer.
    """
    line = line.rstrip()
    tokens = line.split()
    if not tokens:
        return None

    # Detailed variant: last 5 tokens are all numeric.
    if len(tokens) >= 6 and all(t.replace(",", "").lstrip("-").isdigit() for t in tokens[-5:]):
        candidate = " ".join(tokens[:-5])
        counts = [int(t.replace(",", "")) for t in tokens[-5:]]
        return candidate.strip(), counts

    # Totals-only variant: last token is numeric.
    if len(tokens) >= 2 and tokens[-1].replace(",", "").lstrip("-").isdigit():
        candidate = " ".join(tokens[:-1])
        counts = [int(tokens[-1].replace(",", ""))]
        return candidate.strip(), counts

    return None


def _next_nonblank(lines: list[str], start: int) -> int:
    """Return index of the next non-empty line, or len(lines) if none."""
    i = start
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i


def parse_county(county: str, lookup: dict) -> list[dict]:
    """Extract precinct results from one county's Electionware PDF."""
    pdf_path = SOURCE_DIR / f"{county}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    if county in OCR_COUNTIES:
        text = extract_text_ocr(pdf_path)
    else:
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

        # Precinct lines start with a code like A101.
        m = PRECINCT_RE.match(line)
        if m:
            current_precinct = m.group(1)
            # Ignore any trailing report metadata in the precinct name.
            current_precinct = re.sub(r"\s+\d+\s+of\s+\d+.*$", "", current_precinct)
            rest = m.group(2).strip()
            # Some PDFs append the office to the precinct line:
            #     C102 West Brodhead, QUESTION
            # Split it off if the suffix is really an office.
            if "," in rest:
                name_part, _, office_part = rest.rpartition(",")
                office_part = office_part.strip()
                nxt = _next_nonblank(lines, i + 1)
                if nxt < len(lines) and VOTE_FOR_RE.match(lines[nxt].strip()):
                    current_precinct = current_precinct  # keep the code only
                    raw_office = office_part
                    m_off = OFFICE_RE.match(raw_office)
                    if m_off:
                        party_code = m_off.group(1).upper()
                        raw_office = m_off.group(2).strip()
                        current_party = PARTY_MAP.get(party_code, party_code)
                    else:
                        current_party = ""
                    current_district = extract_district(raw_office)
                    current_office = normalize_office(raw_office)
            i += 1
            continue

        # Office lines are always followed by "Vote For".
        nxt = _next_nonblank(lines, i + 1)
        if nxt < len(lines) and VOTE_FOR_RE.match(lines[nxt].strip()):
            raw_office = line
            m_off = OFFICE_RE.match(raw_office)
            if m_off:
                party_code = m_off.group(1).upper()
                raw_office = m_off.group(2).strip()
                current_party = PARTY_MAP.get(party_code, party_code)
            else:
                current_party = ""
            current_district = extract_district(raw_office)
            current_office = normalize_office(raw_office)
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

        # Correct OCR mangled candidate names and pull district/party.
        matched_candidate, matched_district, matched_party = fuzzy_match_candidate(
            county, current_office, candidate, lookup
        )
        if matched_candidate:
            candidate = matched_candidate
        if matched_district:
            current_district = matched_district
        if matched_party:
            current_party = matched_party

        if len(counts) == 5:
            total, mail, ev_excused, ev_unexcused, election_day = counts
            early_voting = ev_excused + ev_unexcused
            absentee_mail = mail
            absentee = ""
        elif len(counts) == 1:
            total = counts[0]
            early_voting = ""
            election_day = ""
            absentee_mail = ""
            absentee = ""
        else:
            i += 1
            continue

        # Backfill district/party from the county totals file when missing.
        district = current_district
        party = current_party
        key = (county, current_office, candidate)
        if key in lookup:
            if not district:
                district = lookup[key]["district"]
            if not party:
                party = lookup[key]["party"]

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
                "absentee_mail": absentee_mail,
                "absentee": absentee,
            }
        )
        i += 1

    if county in OCR_COUNTIES:
        rows = deduplicate_ocr_candidates(rows)

    return rows


def write_county_csv(county: str, rows: list[dict]) -> Path:
    """Write the parsed rows to the canonical per-county precinct CSV."""
    out_path = OUT_DIR / f"20260519__ky__primary__{county.lower()}__precinct.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "county", "precinct", "office", "district", "party", "candidate",
        "votes", "early_voting", "election_day", "absentee_mail", "absentee",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def main(counties: list[str] | None = None):
    lookup = load_county_lookup(COUNTY_CSV)
    target = (
        counties
        if counties
        else DETAILED_COUNTIES + TOTALS_ONLY_COUNTIES + OCR_COUNTIES
    )
    for county in target:
        try:
            rows = parse_county(county, lookup)
            out_path = write_county_csv(county, rows)
            print(f"{county}: {len(rows):,} rows -> {out_path}")
        except Exception as e:
            print(f"{county}: ERROR {e}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main(sys.argv[1:] or None)

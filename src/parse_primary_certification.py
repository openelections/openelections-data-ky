#!/usr/bin/env python3
"""
Convert the KY 2026 Primary Certification of Vote Totals PDF into a
county-level results CSV, matching the format of
2018/20180522__ky__primary__county.csv (county,office,district,party,candidate,votes).

Source PDF: openelections-sources-ky/2026/primary/2026 Primary Certification of Vote Totals Final.pdf
Uses natural-pdf (https://github.com/jsoma/natural-pdf) for text/position extraction.

Usage:
    uv run python3 parse_primary_certification.py <path-to-pdf> <output-csv>
"""

import csv
import re
import sys
from collections import namedtuple

import natural_pdf as npdf

ELECTION_DATE = "20260519"

TITLE_FRAGMENTS = {
    "Commonwealth of Kentucky",
    "Michael G. Adams, Secretary of State",
    "2026 Primary Election Results",
}

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

OFFICE_ALIASES = {
    "United States Senator": "United States Senator",
    "United States Representative in Congress": "United States Representative",
    "US Representative": "United States Representative",
    "State Senator": "State Senate",
    "State Representative": "State Representative",
    "District Judge": "District Judge",
}

Word = namedtuple("Word", "text top x0 x1 bold size")


def load_words(page):
    words = []
    for w in page.find_all("word"):
        words.append(Word(w.text, w.top, w.x0, w.x1, bool(getattr(w, "bold", False)),
                           round(getattr(w, "size", 0), 1)))
    return words


def format_candidate_name(parts):
    """Reorder a candidate's fields (source order varies by race) into the
    OpenElections convention: given name(s) in title case, followed by the
    all-caps surname, e.g. "Andy BARR"."""
    def is_caps(text):
        letters = [c for c in text if c.isalpha()]
        return bool(letters) and all(c.isupper() for c in letters)

    given = [p for p in parts if p and not is_caps(p)]
    surname = [p for p in parts if p and is_caps(p)]
    return re.sub(r"\s+", " ", " ".join(given + surname)).strip()


def is_party_line(text):
    return text == "Nonpartisan" or text.endswith("Party")


def leading_number(text):
    m = re.search(r"(\d+)", text)
    return m.group(1) if m else ""


def normalize_office(office_line, district_lines):
    office = OFFICE_ALIASES.get(office_line, office_line)
    if office_line == "District Judge":
        judicial_district = district_lines[0] if district_lines else ""
        division = district_lines[1] if len(district_lines) > 1 else ""
        return f"District Judge, {judicial_district}", leading_number(division)
    district = leading_number(district_lines[0]) if district_lines else ""
    return office, district


def normalize_party(party_line):
    if party_line == "Nonpartisan":
        return ""
    return party_line.replace(" Party", "")


def find_blocks(words):
    """Find masthead (office/district/party) blocks on a page, in top order."""
    bold12 = sorted(
        (w for w in words if w.bold and w.size == 12.0 and w.text not in TITLE_FRAGMENTS),
        key=lambda w: w.top,
    )
    blocks = []
    current = []
    for w in bold12:
        current.append(w)
        if is_party_line(w.text):
            office_line = current[0].text
            district_lines = [c.text for c in current[1:-1]]
            party_line = current[-1].text
            office, district = normalize_office(office_line, district_lines)
            party = normalize_party(party_line)
            blocks.append({
                "top": current[0].top,
                "content_start": current[-1].top + 13.8,
                "office": office,
                "district": district,
                "party": party,
            })
            current = []
    return blocks


def cluster_positions(xs, tolerance=4.0):
    """Cluster a list of x positions into sorted column centers."""
    xs = sorted(xs)
    clusters = []
    for x in xs:
        if clusters and x - clusters[-1][-1] <= tolerance:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [sum(c) / len(c) for c in clusters]


def optimal_partition(xs, k):
    """Split sorted xs into k contiguous, left-to-right groups minimizing the
    total within-group sum-of-squares (1D k-means via dynamic programming).
    Returns a list of k (start, end) index pairs into xs."""
    n = len(xs)
    prefix = [0.0] * (n + 1)
    prefix2 = [0.0] * (n + 1)
    for i, x in enumerate(xs):
        prefix[i + 1] = prefix[i] + x
        prefix2[i + 1] = prefix2[i] + x * x

    def cost(i, j):
        m = j - i
        if m <= 0:
            return 0.0
        s = prefix[j] - prefix[i]
        s2 = prefix2[j] - prefix2[i]
        return s2 - (s * s) / m

    INF = float("inf")
    dp = [[INF] * (k + 1) for _ in range(n + 1)]
    split = [[0] * (k + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for j in range(1, k + 1):
        for i in range(j, n + 1):
            best, bestp = INF, j - 1
            for p in range(j - 1, i):
                c = dp[p][j - 1] + cost(p, i)
                if c < best:
                    best, bestp = c, p
            dp[i][j] = best
            split[i][j] = bestp

    groups = []
    i, j = n, k
    while j > 0:
        p = split[i][j]
        groups.append((p, i))
        i, j = p, j - 1
    groups.reverse()
    return groups


def nearest_index(x, centers):
    best_i, best_d = 0, abs(x - centers[0])
    for i, c in enumerate(centers[1:], start=1):
        d = abs(x - c)
        if d < best_d:
            best_i, best_d = i, d
    return best_i


def group_rows(words, tolerance=2.0):
    """Group words into visual rows by top position."""
    rows = {}
    for w in sorted(words, key=lambda w: w.top):
        placed = False
        for key in rows:
            if abs(key - w.top) <= tolerance:
                rows[key].append(w)
                placed = True
                break
        if not placed:
            rows[w.top] = [w]
    return [sorted(rows[k], key=lambda w: w.x0) for k in sorted(rows)]


def extract_zone_results(words, section):
    """Given all words in a zone (one office/district/party section on one page),
    return list of (county, candidate, votes) tuples."""
    rows = group_rows(words)

    numeric_re = re.compile(r"^[\d,]+$")

    def is_data_row(row):
        # A few KY counties (Christian, Casey, Clay, Bell, ...) are also
        # given names, so also require the rest of the row to be numbers.
        return (row and row[0].text in COUNTIES and len(row) > 1
                and all(numeric_re.match(w.text) for w in row[1:]))

    data_rows = [r for r in rows if is_data_row(r)]
    if not data_rows:
        return []

    first_data_top = min(r[0].top for r in data_rows)
    header_words = [w for w in words if w.top < first_data_top]

    # Vote numbers are right-justified within their column, so the right
    # edge (x1) is the stable anchor across rows with different digit counts.
    vote_xs = []
    for r in data_rows:
        for w in r[1:]:
            vote_xs.append(w.x1)
    vote_cols = cluster_positions(vote_xs, tolerance=8.0)
    if not vote_cols:
        return []

    # Header candidate names are laid out in narrow columns: depending on
    # name length, a candidate's surname/given-name/suffix fields may each
    # be a single whole word, or may wrap character-by-character down the
    # column (in which case every letter -- and any literal space -- is its
    # own word). Partition all header words by x-position into exactly as
    # many contiguous, left-to-right groups as there are vote columns (1D
    # k-means), which is robust to both layouts and to how tightly/loosely
    # a given race's fields happen to be spaced.
    # A field's *right* edge (x1) is the stable anchor: short given names are
    # left-aligned but long surnames/suffixes are right-aligned to match, so
    # x1 lines up across a candidate's fields (and across a wrapped field's
    # stacked characters) far more reliably than x0 does.
    n_candidates = len(vote_cols)
    if len(header_words) < n_candidates:
        return []
    header_words_sorted = sorted(header_words, key=lambda w: w.x1)
    xs = [w.x1 for w in header_words_sorted]
    groups = optimal_partition(xs, n_candidates)

    def join_by_top(items):
        """Join word-like items (sorted by top) into one string. Consecutive
        single characters are concatenated directly (they're spelling one
        word top-to-bottom, and any literal spaces are their own tokens);
        anything else gets a space separator."""
        pieces = []
        prev_single_char = False
        for i, item in enumerate(items):
            is_single_char = len(item.text) == 1
            if i > 0 and not (prev_single_char and is_single_char):
                pieces.append(" ")
            pieces.append(item.text)
            prev_single_char = is_single_char
        return "".join(pieces)

    candidates = []
    for start, end in groups:
        group_words = header_words_sorted[start:end]
        # Within a candidate's group, fields (surname, given name, suffix)
        # occupy their own narrow x-position; sub-cluster on x0 so that a
        # character-wrapped field's letters (identical x0 across rows)
        # aren't interleaved-by-top with a neighboring field's letters.
        sub_cols = []
        for w in sorted(group_words, key=lambda w: (w.x1, w.top)):
            if sub_cols and abs(w.x1 - sub_cols[-1][-1].x1) <= 3.0:
                sub_cols[-1].append(w)
            else:
                sub_cols.append([w])
        sub_col_texts = [
            join_by_top(sorted(sc, key=lambda w: w.top))
            for sc in sorted(sub_cols, key=lambda sc: sc[0].x1)
        ]
        candidates.append(format_candidate_name(sub_col_texts))

    results = []
    for r in data_rows:
        county = r[0].text
        col_values = {}
        for w in r[1:]:
            idx = nearest_index(w.x1, vote_cols)
            col_values[idx] = w.text.replace(",", "")
        for i in range(len(vote_cols)):
            candidate = candidates[i]
            if not candidate:
                continue
            votes = col_values.get(i, "")
            results.append((county, section["office"], section["district"],
                             section["party"], candidate, votes))
    return results


def parse_pdf(pdf_path):
    pdf = npdf.PDF(pdf_path)
    all_results = []
    current_section = None

    for page in pdf.pages:
        words = load_words(page)
        masthead_words = {w for w in words if w.bold and w.size == 12.0}
        blocks = find_blocks(words)

        content_words = [w for w in words if w not in masthead_words]

        if not blocks:
            if current_section is not None:
                all_results.extend(extract_zone_results(content_words, current_section))
            continue

        zone_start = 0.0
        if blocks[0]["top"] > 0 and current_section is not None:
            leading_words = [w for w in content_words if w.top < blocks[0]["top"]]
            all_results.extend(extract_zone_results(leading_words, current_section))

        for i, block in enumerate(blocks):
            zone_end = blocks[i + 1]["top"] if i + 1 < len(blocks) else float("inf")
            zone_words = [w for w in content_words
                          if block["content_start"] <= w.top < zone_end]
            all_results.extend(extract_zone_results(zone_words, block))
            current_section = block

    return all_results


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <path-to-pdf> <output-csv>", file=sys.stderr)
        sys.exit(1)

    pdf_path, out_path = sys.argv[1], sys.argv[2]
    results = parse_pdf(pdf_path)

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["county", "office", "district", "party", "candidate", "votes"])
        for row in results:
            writer.writerow(row)

    print(f"Wrote {len(results)} rows to {out_path}")


if __name__ == "__main__":
    main()

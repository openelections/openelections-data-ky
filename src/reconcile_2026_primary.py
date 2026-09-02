#!/usr/bin/env python3
"""
Reconcile KY 2026 primary precinct CSVs against the county-level totals file.

County file:  {year}/{date}__ky__{election}__county.csv
Precinct files: {year}/counties/{date}__ky__{election}__{county}__precinct.csv

The county file is intentionally scoped to federal + state legislative + judicial
offices; the precinct files additionally carry local offices and administrative
rows (Over Votes / Under Votes / Ballots Cast).  See 2026/RECONCILIATION.md.

For each (county, office, district, party, candidate) key the script sums votes
across all precinct files and compares the sum to the county file, then reports:

  1. matched keys
  2. vote mismatches (same key, different total)
  3. county-only keys (in the county file, absent from precinct files)
  4. precinct-only keys, split into in-scope offices (a data gap in the county
     file) vs. local offices (expected, by design)
  5. suspected county-total rows: precinct rows named "Absentee" with no
     vote-type breakdowns whose total equals the rest of the county - the
     Larue/Clinton failure pattern where a county total masquerades as a
     precinct row and double-counts the race

Exits non-zero if any vote mismatch, county-only key, or in-scope precinct-only
key is found.

Usage:
    uv run python3 src/reconcile_2026_primary.py [--year 2026] [--date 20260519] [--election primary]
    uv run python3 src/reconcile_2026_primary.py --repo /path/to/openelections-data-ky
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

# Offices the county file is scoped to.  Precinct-only rows for anything else
# are local races and are expected to be absent from the county file.
IN_SCOPE_OFFICES = ("U.S. Senate", "U.S. House", "State Senate", "State Representative")

# Candidate values that are administrative tallies, not candidates.
ADMIN_CANDIDATES = ("Over Votes", "Under Votes")

# Offices that are counted rows but not candidate rows.
ADMIN_OFFICES = ("Ballots Cast",)

# Precinct names that have historically carried county totals by mistake.
SUSPECT_PRECINCT_NAMES = ("Absentee",)


def is_in_scope(office: str) -> bool:
    return office in IN_SCOPE_OFFICES or office.startswith("District Judge")


def is_admin_row(row: dict) -> bool:
    return (
        row["candidate"] in ADMIN_CANDIDATES
        or row["office"] in ADMIN_OFFICES
    )


def load_county_totals(path: Path) -> dict:
    """Return {(county, office, district, party, candidate): votes}."""
    totals = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (
                row["county"].strip(),
                row["office"].strip(),
                row["district"].strip(),
                row["party"].strip(),
                row["candidate"].strip(),
            )
            totals[key] = int(row["votes"].replace(",", ""))
    return totals


def load_precincts(county_glob: Path):
    """Aggregate real candidate rows across precinct files.

    Returns (sums, suspects) where sums maps the county-file key to a vote
    total and suspects lists (path, key) pairs for rows that look like county
    totals masquerading as precinct rows.
    """
    sums = defaultdict(int)
    row_votes = defaultdict(list)  # key -> [(precinct, votes)]
    suspects = []

    files = sorted(county_glob.parent.glob(county_glob.name))
    if not files:
        raise SystemExit(f"No precinct files matched {county_glob}")

    for path in files:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                key = (
                    row["county"].strip(),
                    row["office"].strip(),
                    row["district"].strip(),
                    row["party"].strip(),
                    row["candidate"].strip(),
                )
                if is_admin_row(row):
                    continue
                votes = int(row["votes"].replace(",", ""))
                sums[key] += votes
                row_votes[key].append((row["precinct"].strip(), votes, path, row))

    for key, rows in row_votes.items():
        other_total = sum(v for precinct, v, _, _ in rows
                          if precinct not in SUSPECT_PRECINCT_NAMES)
        for precinct, votes, path, row in rows:
            if (precinct in SUSPECT_PRECINCT_NAMES
                    and len(rows) > 1
                    and votes == other_total
                    and not any(row.get(col, "").strip()
                                for col in ("early_voting", "election_day",
                                            "absentee_mail", "absentee",
                                            "mail", "provisional"))):
                suspects.append((path.name, key, votes))

    return sums, suspects


def main(argv=None) -> int:
    default_repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--repo", type=Path, default=default_repo,
                        help="openelections-data-ky checkout (default: this repo)")
    parser.add_argument("--year", default="2026")
    parser.add_argument("--date", default="20260519")
    parser.add_argument("--election", default="primary")
    args = parser.parse_args(argv)

    county_path = args.repo / f"{args.year}/{args.date}__ky__{args.election}__county.csv"
    precinct_glob = (args.repo / f"{args.year}/counties"
                     / f"{args.date}__ky__{args.election}__*__precinct.csv")

    if not county_path.exists():
        print(f"County totals file not found: {county_path}", file=sys.stderr)
        return 2

    county = load_county_totals(county_path)
    precinct, suspects = load_precincts(precinct_glob)

    matched = vote_mismatches = county_only = 0
    mismatch_rows = []
    for key, expected in county.items():
        actual = precinct.get(key)
        if actual is None:
            county_only += 1
        elif actual == expected:
            matched += 1
        else:
            vote_mismatches += 1
            mismatch_rows.append((key, expected, actual))

    precinct_only_in_scope = []
    precinct_only_local = 0
    for key in precinct:
        if key in county:
            continue
        if is_in_scope(key[1]):
            precinct_only_in_scope.append((key, precinct[key]))
        else:
            precinct_only_local += 1

    print(f"Precinct files: {len(sorted(precinct_glob.parent.glob(precinct_glob.name)))}")
    print(f"County keys: {len(county)}")
    print(f"1. Matched: {matched}")
    print(f"2. Vote mismatches: {vote_mismatches}")
    print(f"3. County-only keys: {county_only}")
    print(f"4. Precinct-only keys: {len(precinct_only_in_scope)} in-scope (gaps in county file), "
          f"{precinct_only_local} local-office (expected)")
    print(f"5. Suspected county-total precinct rows: {len(suspects)}")

    for key, expected, actual in mismatch_rows:
        print(f"  MISMATCH {key}: county={expected} precinct={actual}")
    for key, votes in precinct_only_in_scope:
        print(f"  IN-SCOPE GAP {key}: {votes}")
    for name, key, votes in suspects:
        print(f"  SUSPECT county-total row in {name}: {key} = {votes}")

    failures = vote_mismatches + county_only + len(precinct_only_in_scope) + len(suspects)
    if failures:
        print(f"\n{failures} reconciliation failure(s).")
        return 1
    print("\nReconciliation clean: all county totals match precinct sums, "
          "no gaps in either direction for in-scope offices.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
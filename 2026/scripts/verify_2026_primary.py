#!/usr/bin/env python3
"""
Verify KY 2026 primary precinct CSVs against county-level totals.

County totals: openelections-data-ky/2026/20260519__ky__primary__county.csv
Precinct files: openelections-data-ky/2026/counties/20260519__ky__primary__{county}__precinct.csv

The verifier aggregates votes per (county, office, district, candidate) from the
precinct files and compares them to the corresponding county totals.  Rows for
pseudo-candidates (Under Votes, Over Votes, Ballots Cast) and any candidate
named "Total Votes" are ignored.

Usage:
    uv run python3 verify_2026_primary.py
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

PRECINCT_DIR = Path("/Users/dwillis/code/openelections-data-ky/2026/counties")
COUNTY_TOTALS_PATH = Path("/Users/dwillis/code/openelections-data-ky/2026/20260519__ky__primary__county.csv")

PSEUDO_CANDIDATES = {"Under Votes", "Over Votes", "Ballots Cast", "Total Votes"}


def load_county_totals(path):
    """Return a dict keyed by (county, office, district, candidate) -> votes."""
    totals = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (
                row["county"].strip(),
                row["office"].strip(),
                row["district"].strip(),
                row["candidate"].strip(),
            )
            totals[key] = int(row["votes"].replace(",", ""))
    return totals


def load_precinct_votes(precinct_dir):
    """Aggregate votes from all precinct CSVs."""
    agg = defaultdict(int)
    files = sorted(precinct_dir.glob("20260519__ky__primary__*__precinct.csv"))
    for path in files:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                candidate = row.get("candidate", "").strip()
                if candidate in PSEUDO_CANDIDATES:
                    continue
                votes = row.get("votes", "").strip().replace(",", "")
                if not votes:
                    continue
                key = (
                    row["county"].strip(),
                    row["office"].strip(),
                    row.get("district", "").strip(),
                    candidate,
                )
                agg[key] += int(votes)
    return agg


def main():
    if not COUNTY_TOTALS_PATH.exists():
        print(f"County totals file not found: {COUNTY_TOTALS_PATH}", file=sys.stderr)
        sys.exit(1)
    if not PRECINCT_DIR.exists():
        print(f"Precinct directory not found: {PRECINCT_DIR}", file=sys.stderr)
        sys.exit(1)

    totals = load_county_totals(COUNTY_TOTALS_PATH)
    precinct = load_precinct_votes(PRECINCT_DIR)

    matched = 0
    mismatched = []
    missing_from_precincts = []
    missing_from_totals = []

    for key, expected in totals.items():
        if key not in precinct:
            missing_from_precincts.append((key, expected))
            continue
        actual = precinct[key]
        if actual == expected:
            matched += 1
        else:
            mismatched.append((key, expected, actual, actual - expected))

    for key, actual in precinct.items():
        if key not in totals:
            missing_from_totals.append((key, actual))

    print(f"County totals checked: {len(totals)}")
    print(f"Matched: {matched}")
    print(f"Mismatched: {len(mismatched)}")
    print(f"Missing from precinct files: {len(missing_from_precincts)}")
    print(f"In precinct files but not county totals: {len(missing_from_totals)}")

    if mismatched:
        print("\nMismatched candidate/county totals:")
        print(f"{'County':<12} {'Office':<28} {'District':<8} {'Candidate':<30} {'Expected':>10} {'Actual':>10} {'Diff':>10}")
        for (county, office, district, candidate), expected, actual, diff in sorted(mismatched):
            print(f"{county:<12} {office:<28} {district:<8} {candidate:<30} {expected:>10} {actual:>10} {diff:>+10}")

    if missing_from_precincts:
        print("\nCandidates present in county totals but missing from precinct files:")
        for (county, office, district, candidate), expected in sorted(missing_from_precincts):
            print(f"  {county} | {office} | district {district} | {candidate} | expected {expected}")

    if missing_from_totals:
        print("\nCandidates present in precinct files but not in county totals:")
        for (county, office, district, candidate), actual in sorted(missing_from_totals):
            print(f"  {county} | {office} | district {district} | {candidate} | actual {actual}")

    if mismatched or missing_from_precincts:
        sys.exit(1)
    print("\nAll verified candidate/county totals match.")


if __name__ == "__main__":
    main()

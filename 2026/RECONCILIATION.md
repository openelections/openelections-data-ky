# 2026 Primary (2026-05-19) Reconciliation Notes

The 2026 primary ships two layers of results that must agree:

- `20260519__ky__primary__county.csv` — county-level totals.
- `counties/20260519__ky__primary__{county}__precinct.csv` — 120 per-county
  precinct files (a superset; see Scope below).

Reconcile them with:

```bash
uv run python3 src/reconcile_2026_primary.py
```

The script sums precinct votes per `(county, office, district, party,
candidate)` and diffs against the county file. **As of 2026-09-01 the
reconciliation is clean: all 3,194 county keys match the precinct sums
exactly — 0 vote mismatches, 0 keys missing from either layer for in-scope
offices, and no suspected county-total rows hiding in the precinct files.**

## Scope of the county file

The county file was generated from the SBE *Certification of Vote Totals*
PDF (`openelections-sources-ky/2026/primary/`) and covers **federal +
state legislative + judicial** offices only: U.S. Senate, U.S. House,
State Senate, State Representative, and District Judge. **Local offices
(Sheriff, Magistrate, Jailer, Mayor, city councils, etc.) are deliberately
excluded** and appear only in the precinct files, as do the administrative
`Over Votes` / `Under Votes` / `Ballots Cast` rows.

## Discrepancies found and resolved

1. **Larue — State Senate 14 (Malcolm W. JONES).** The precinct file
   carried the real per-precinct rows under the typo spelling `Malcom W.
   JONES` with a blank party, plus a single `Absentee` row that was a
   county total (447) masquerading as a precinct — double-counting the
   race. Fixed: spelling corrected, party set to `Democratic`, duplicate
   summary row deleted. The county file's 447 was always correct.

2. **District Judge labels.** Clark used `District Judge 25th Judicial
   District 1st Divison` (typo) and Madison/Clinton used a bare
   `District Judge`. All normalized to the canonical
   `District Judge, Nth Judicial District` form with the division number
   in the `district` column, matching Daviess/Fayette/Russell/Wayne.

3. **Clinton — "two" judge races were one.** The bare-`District Judge`
   precinct rows and the `District Judge, 40th Judicial District` label
   (which appeared only on county-total `Absentee` rows, the same pattern
   as Larue) were the same race. The summary rows were deleted and the
   precinct rows relabeled; totals (SIMMONS 1564, WHITTENBURG 479,
   BRADSHAW 1048 county-wide) were never wrong.

4. **25th Judicial District judge race.** One race (Clark + Madison),
   1st Division, nonpartisan. Micah Johnson withdrew too late for ballot
   removal, so Madison's results report three candidates (JOHNSON 2777,
   BOTTS 2162, FRAZIER 10199) while Clark's official results report two
   (BOTTS 1151, FRAZIER 3221) — Clark's file is complete as converted.
   The SBE certification omits this race (with only two candidates
   remaining after the withdrawal, both advance to November and the
   primary was canceled as a nominating contest), so the county-file rows
   were aggregated from the precinct files. Added to the county file.

5. **Uncontested State Representative races 45 and 62.** Also absent
   from the SBE certification (uncontested races are omitted), present
   in the precinct files. Added to the county file from precinct sums:
   State Rep 45 — Killian TIMONEY (Republican): Fayette 1796,
   Jessamine 349. State Rep 62 — Randy Jackson SIMPKINS (Democratic):
   Scott 1663. The source exports left `party` blank for both; the
   parties were filled from public reporting (Herald-Leader /
   Ballotpedia: Timoney ran in the GOP primary after Jeff Thompson
   withdrew; Simpkins was the unopposed Democratic candidate) in both
   the precinct files and the county file.

6. **Local office-name normalization.** Precinct-file office labels were
   normalized across all 120 counties: `County Judge Executive` and bare
   `Judge Executive` → `County Judge/Executive`; `City OF`/`City Of` →
   `City of`; `Justice OF THE Peace` → `Justice of the Peace`;
   `Magistrate/Constable/County Commissioner Dist. N` → `District N`;
   `3Rd`/`4Th` → `3rd`/`4th`. No vote values were touched; every row was
   verified identical to its pre-normalization form apart from the office
   string.

## Known non-issues

- The Jefferson precinct file has an extra `provisional` column; the
  other 119 files stop at `absentee`.
- Bare `Magistrate` and `Constable` rows (no district number in the
  office name or `district` column) in counties where the source exports
  did not label magisterial districts.
- Madison lacks `Over Votes`/`Under Votes` rows for the 25th JD judge
  race (Clark has them), and its `Constable 3rd/4th Magisterial
  District` rows leave the `district` column empty.
- Precinct CSVs use CRLF line endings.
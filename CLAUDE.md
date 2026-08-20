# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This is an OpenElections data repository containing pre-processed Kentucky election results. It is not a deployable application; the primary artifacts are CSV data files organized by election year. The repository also contains ad-hoc scripts used to convert source materials (PDFs, Clarity Elections XML/Excel exports, and fixed-width text files) into the standardized CSV format.

Results are mostly converted from PDFs published by the Kentucky State Board of Elections and from Clarity Elections night-reporting exports. Many source files are labeled "unofficial", but they have been verified with county clerks and are treated here as official results.

## Data file layout and naming

CSV files live in year-named directories at the repository root.

Common precinct result file patterns:

- `YYYY/YYYYMMDD__ky__{primary|general}__{county}__precinct.csv` — per-county precinct results. This is the most common form.
- `YYYY/YYYYMMDD__ky__{primary|general}__precinct.csv` — statewide precinct results, combining all counties.
- `YYYY/YYYYMMDD__ky__{primary|general}__county.csv` — county-level aggregated results.

Other data files:

- `YYYY/ky_registered_voters_precinct_{election}_YYYY.csv` — registered voter counts by precinct.
- `YYYY/turnout_YYYY__ky__{primary|general}__precinct.csv` — turnout counts by precinct.

Canonical precinct result header:

```
county,precinct,office,district,party,candidate,votes
```

Newer files may include vote-type breakdown columns after `votes`, such as `election_day`, `absentee`, `early_voting`, `mail`, and `provisional`. Older files omit these breakdowns.

Candidate names follow the OpenElections convention used here: first name in title case and last name in all caps, e.g. `Matt BEVIN`, `Mitch McCONNELL`, `Donald J. TRUMP`.

## Validation

The repository is validated by the shared `openelections/openelections-data-tests` test suite. Tests run automatically via GitHub Actions on every push and pull request.

The repository uses `uv` to manage Python dependencies for the helper scripts. Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. The validation tests themselves still come from the external `openelections/openelections-data-tests` repo, which must be checked out separately.

### Python tooling

- Run a script through `uv` without manually activating an environment:

  ```bash
  uv run python3 src/convertToCsv.py path/to/spreadsheet.xml ...
  ```

- Add a new Python dependency:

  ```bash
  uv add <package>
  ```

  This updates `pyproject.toml` and `uv.lock`. Commit both files together.

### Running tests locally

1. Check out the data tests repo at a known version:

   ```bash
   git clone --branch v2.2.0 https://github.com/openelections/openelections-data-tests.git ../data_tests
   ```

2. Run the full test suite:

   ```bash
   REPO=/Users/dwillis/code/openelections-data-ky
   python3 ../data_tests/run_tests.py --group-failures --log-file=file_format.txt    file_format    "$REPO"
   python3 ../data_tests/run_tests.py --group-failures --log-file=duplicate_entries.txt duplicate_entries "$REPO"
   python3 ../data_tests/run_tests.py --group-failures --log-file=missing_values.txt  missing_values  "$REPO"
   python3 ../data_tests/run_tests.py --group-failures --log-file=vote_breakdown_totals.txt vote_breakdown_totals "$REPO"
   ```

3. Run a single test on a single changed file:

   ```bash
   python3 ../data_tests/run_tests.py \
     --files 2024/20241105__ky__general__precinct.csv \
     --group-failures \
     --log-file=file_format.txt \
     --truncate-log-file \
     file_format "$REPO"
   ```

Available tests:

- `file_format` — validates file naming, headers, and CSV structure.
- `duplicate_entries` — detects duplicate rows.
- `missing_values` — checks that required values are present.
- `vote_breakdown_totals` — flags rows where vote-type breakdowns exceed the total, and checks equality when headers match known schemas.

## Data conversion scripts

The repo contains helper scripts from past data-entry efforts. They are not a formal build pipeline and often contain hardcoded paths or election-specific logic, so treat them as reference or starting points rather than reusable CLI tools.

- `src/convertToCsv.py` — Converts XML Excel 2003 spreadsheets into the canonical precinct CSV format. Run with one or more `.xml` spreadsheet files and it writes `output.csv`.

  ```bash
  uv run python3 src/convertToCsv.py path/to/spreadsheet.xml ...
  ```

- `clarity_parser.py` — Downloads and parses Clarity Elections `detailxml.zip` results into the canonical CSV format.

- `clarity_excel_parser.py` — Parses a locally saved Clarity Elections `.xls` Excel file into a county precinct CSV.

- `src/TxtFileParser.cs` and `src/2023PrimaryA.cs` — C# console apps for parsing fixed-width text files and 2023 primary extracts. They require the `CsvHelper` NuGet package and contain hardcoded input/output paths that must be updated before running.

- `src/jeff_co_ky_scraper.R` — R script that processes tabulizer-extracted Jefferson County PDF tables. It depends on the saved workspace in `src/scraped_jeff_co_pdf.rda`.

## OCR

Use **PaddleOCR** for all OCR work. It is the project's designated OCR library and is managed via `uv` (see `pyproject.toml`). Do not introduce other OCR libraries such as Tesseract, pytesseract, or EasyOCR unless explicitly approved.

Run PaddleOCR through `uv run`:

```bash
uv run python3 -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(use_angle_cls=True, lang='en'); result = ocr.ocr('path/to/image.png')"
```

When adding new OCR-based conversion scripts, import from `paddleocr` and keep any language or model settings consistent across scripts.

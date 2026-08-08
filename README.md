# WCWH Water Quality Reports

Generates personalized, bilingual (English / Spanish) drinking-water quality PDF reports for
participants in the Whole Communities–Whole Health (WCWH) study.

Given a batch of lab results in an Excel workbook, the pipeline produces one PDF per
participant/sample-date containing their measured values, how those values compare to
regulatory limits, and how they compare to the community average.

## PDF design goals

These reports are designed primarily for viewing on phones rather than for printing on
standard Letter or A4 paper. The PDF behaves like a downloadable, linkable mobile report:

- The page width is approximately 377 CSS pixels to match a comfortable mobile reading width.
- Each report section is rendered as its own PDF page, and each page's height adapts to its
  content so short sections do not leave large areas of empty space.
- The table of contents and internal links remain usable inside the downloaded PDF.
- PDF remains the distribution format so a report can be downloaded, shared, and archived.

This variable-height page model is the main reason the pipeline uses **WeasyPrint**. Browser
PDF printing produces a fixed page size shared by every page, while WeasyPrint's named-page
support allows the report to assign a different height to each section without giving up PDF
navigation or the phone-friendly width.

---

## Pipeline

```
data/sources/<batch>.xlsx
        │
        │  ① data_analysis.py        pandas
        ▼
build/<batch>/records.json           flat per-participant records
        │
        │  ② bar-gen.js              node + puppeteer + sharp
        ▼
build/<batch>/bars/<ID>/<date>/*.png     one scale bar per parameter × location
        │
        │  ③ report_gen.py           jinja2 + beautifulsoup + selenium + weasyprint
        ▼
reports/<batch>/WATER.<ID>.<YYYY.MM.DD>.pdf     (AGUA.* for Spanish)
```

### How the stages find their files

A run is identified by exactly one thing: **the batch name**, which is the basename of the
input workbook. `settings.resolve()` derives every path from it, `run_pipeline.py` writes the
result to `build/<batch>/manifest.json`, and all three stages read that one file via a single
environment variable:

```bash
MANIFEST='build/B8 Data/manifest.json'
```

```jsonc
{
  "batch":   "B8 Data",
  "source":  ".../data/sources/B8 Data.xlsx",
  "records": ".../build/B8 Data/records.json",
  "bars":    ".../build/B8 Data/bars",
  "work":    ".../build/work",
  "reports": ".../reports/B8 Data"
}
```

There are no fallback defaults. A stage started without `MANIFEST` exits with an error rather
than guessing a batch — guessing is how a run silently overwrites a different batch's output.

`settings.py` is the only module that builds paths. Moving a directory is a one-line change
there; nothing else hardcodes the layout, including the template (see below).

### ① `data_analysis.py`
- Reads the source workbook; maps numeric participant numbers to internal IDs
  (`P0088T`, …) using `data/reference/Participant_Hornsense_ID_Map.xlsx`.
- Groups rows by `(Participant_ID, Sample_date)` and splits each group into three sample
  locations: **Outdoor** (outdoor tap), **FF** (indoor first flush), **Filtered**.
- First pass computes community averages (with separate cohorts for chlorine- vs
  chloramine-disinfected systems); second pass builds the per-participant record.
- Applies pass/fail checks from `config.json` and resolves the virtual `Disinfectant`
  parameter to either `Chlorine_*` or `Chloramine_*` depending on the utility.
- Writes `build/<batch>/records.json`.

### ② `bar-gen.js`
Renders each parameter's horizontal scale bar (acceptable range in green, measured value as a
dot) in headless Chrome via Puppeteer and screenshots it to PNG. Spanish records get labels
translated from `data/reference/translations.xlsx`.

Checks that Chrome can actually launch before starting and exits non-zero if it cannot. Set
`DEBUG=1` to also dump each bar's HTML into `debug/`.

### ③ `report_gen.py`
1. Renders `templates/template.html` with Jinja2.
2. For Spanish reports, walks the DOM and substitutes text from `translations.xlsx`, calling
   the Google Translate API for anything missing and **caching new translations back into the
   spreadsheet**.
3. Drops pages whose content is empty and renumbers the table of contents.
4. Measures the real rendered height of each page with headless Chrome (Selenium) and rewrites
   the `@page` heights in `report.css` so WeasyPrint paginates correctly.
5. Shells out to `weasyprint` to produce the PDF and moves it into `reports/<batch>/`.

---

## Setup

### Prerequisites
- Python 3.13
- Node.js (for `bar-gen.js`)
- Google Chrome — used by Selenium in step ③
- WeasyPrint's native libraries. On macOS:
  ```bash
  brew install pango libffi
  ```

### Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
npm install
```

`npm install` also downloads Puppeteer's own Chrome into `~/.cache/puppeteer`. If that cache
is ever cleared, `bar-gen.js` will refuse to start; restore it with:

```bash
npx puppeteer browsers install chrome
```

---

## Running

```bash
.venv/bin/python run_pipeline.py
```

You will be prompted for:

1. **Mode**
   - `1` — full pipeline over a real batch in `data/sources/`
   - `3` — template preview: renders one PDF from mock data into `reports/template/`, useful
     for iterating on `templates/template.html` and `templates/report.css` without touching
     real data. Mode 3 skips step ① and substitutes a fake record; steps ② and ③ are identical
     to a real run.
2. **Batch** — which `.xlsx` in `data/sources/`. Its basename is the batch name and becomes
   the output subdirectory under `reports/`.

To run one stage by hand, point it at an existing manifest:

```bash
MANIFEST='build/B8 Data/manifest.json' .venv/bin/python report_gen.py
```

---

## Layout

| Path | Purpose |
| --- | --- |
| `run_pipeline.py` | Interactive driver for the three steps |
| `settings.py` | Directory layout and batch → path resolution; the only place paths are built |
| `config.json` | All tunable configuration — see below |
| `data_analysis.py` | Step ① — Excel → `records.json` |
| `bar-gen.js` | Step ② — scale-bar PNGs |
| `report_gen.py` | Step ③ — HTML → PDF |
| `height_calculation.py` | Selenium helper that measures rendered element heights |
| `templates/` | `template.html` + `report.css` — the report layout |
| `data/sources/` | Input workbooks, one per batch |
| `data/reference/` | ID map and translation dictionary — lookup tables that outlive any batch |
| `assets/` | `icons/`, `images/`, `fonts/` (Inter) referenced by the report |
| `reports/<batch>/` | Generated PDFs |
| `archive/` | One-off scripts and reference files from earlier batches; not part of the pipeline |

### Generated, not tracked
`build/` holds everything the pipeline produces — records, bars and rendered HTML — and
`debug/` holds the optional bar dumps. Both are gitignored and safe to delete at any time.

`reports/` is also gitignored. The PDFs there are deliverables; the pipeline can regenerate
any batch from `data/sources/`, but back them up before re-running a batch you have already
distributed.

---

## Configuration

Everything tunable lives in `config.json`. No constants are duplicated in the Python or
JavaScript sources, and nothing modifies the config at runtime.

| Key | Purpose |
| --- | --- |
| `parameterRanges` | Acceptable range and bar maximum per parameter |
| `parameterTypes` | Bar style and pass/fail logic per parameter (see table below) |
| `parameters.all` | Parameters shown in the report — used by `report_gen.py` and `bar-gen.js` |
| `parameters.measured` | What `data_analysis.py` computes: `all` plus the raw `Chlorine` and `Chloramine` columns that the virtual `Disinfectant` resolves to |
| `columnMap` | Internal parameter name → column name in the source workbook |
| `barDefaults` | Bar image size, and the axis maximum for unregulated (type 2) parameters |
| `files` | Names of the lookup files in `data/reference/`, and the translation column headers |
| `waterUtilities` | Per-utility contact details, annual-report link and logo (path relative to `assets/`) |

### Parameter types

| Type | Meaning | Examples |
| --- | --- | --- |
| `0` | Banded scale with text labels, no pass/fail | `pH`, `Hardness` |
| `1` | Regulated `[min, max, bar_max]` range | `Lead`, `Nitrate`, `Chlorine` |
| `2` | Measured but unregulated — no range drawn | `Ammonia`, `Temperature` |
| `3` | Must be zero | `Bacteria` |

### Adding a parameter

1. In `config.json`: add it to `parameterRanges`, `parameterTypes`, `parameters.all`,
   `parameters.measured` and `columnMap`.
2. In `templates/template.html`: add one `parameter_box(...)` call and a table-of-contents
   entry.

---

## The report template

`templates/template.html` renders the eight parameter sections through a single macro rather
than repeating the same markup once per parameter. Changing how every parameter section looks
is a change to `parameter_box` (or `parameter_box_binary`, used only by Bacteria); adding a
parameter is one more call.

The template never hardcodes how many `../` segments separate the rendered HTML from the files
it references. `report_gen.py` computes `assets_url` and `bars_url` and passes them in, and
`report.css` uses an `{{ASSETS}}` placeholder for the same reason. If you add an image
reference, use those variables rather than a relative path.

Each parameter's `<article>` wrapper is deliberately left inline, because the wrapper markup
differs between pages (some are inside `.chapter`, some are not) and those differences affect
the rendered width. See the comment block at the top of the template.

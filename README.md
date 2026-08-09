# WCWH Water Quality Reports

Generates personalized, bilingual (English / Spanish) drinking-water quality PDF reports for
participants in the Whole Communities–Whole Health (WCWH) study.

Given a batch of lab results in an Excel workbook, the pipeline produces one PDF per
participant/sample-date containing their measured values, how those values compare to
regulatory limits, and how they compare to the community average.

This is one of what may become several report types sharing the same engine. See
`docs/multi-type-refactor.md` for the engine/type split and the contracts between them.

## PDF design goals

These reports are designed primarily for viewing on phones rather than for printing on
standard Letter or A4 paper. The PDF behaves like a downloadable, linkable mobile report:

- The page width is approximately 377 CSS pixels to match a comfortable mobile reading width —
  shared by every report type, not a water-quality-specific choice.
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
data/sources/<type>/<batch>.xlsx
        │
        │  ① report_types/<type>/analyze.py           pandas
        ▼
build/<type>/<batch>/records.json           flat, render-ready per-participant records
        │
        │  ② report_types/<type>/components/bar-gen.js  node + puppeteer (optional per type)
        ▼
build/<type>/<batch>/bars/<ID>/<date>/*.png     one scale bar per parameter × location
        │
        │  ③ engine/render.py           jinja2 + beautifulsoup + selenium + weasyprint
        ▼
reports/<type>/<batch>/WATER.<ID>.<YYYY.MM.DD>.pdf     (AGUA.* for Spanish)
```

`engine/` has no water-quality-specific knowledge — it only knows the Record contract
(`id` / `date` / `language`) and the template attribute contract (`data-page`,
`data-page-content`, `data-page-number`, `data-toc-entry`, `data-toc-page`). Everything else —
parameter definitions, the bar-chart visuals, the report's copy and layout — lives in
`report_types/water_quality/`.

### How the stages find their files

A run is identified by two things: **the report type** and **the batch name** (the input
file's basename). `engine/paths.resolve()` derives every other path from those two,
`run_pipeline.py` writes the result to `build/<type>/<batch>/manifest.json`, and all three
stages read that one file via a single environment variable:

```bash
MANIFEST='build/water_quality/B8 Data/manifest.json'
```

```jsonc
{
  "type":      "water_quality",
  "batch":     "B8 Data",
  "source":    ".../data/sources/water_quality/B8 Data.xlsx",
  "records":   ".../build/water_quality/B8 Data/records.json",
  "bars":      ".../build/water_quality/B8 Data/bars",
  "work":      ".../build/water_quality/work",
  "reports":   ".../reports/water_quality/B8 Data",
  "type_dir":  ".../report_types/water_quality",
  "templates": ".../report_types/water_quality/templates",
  "assets":    ".../report_types/water_quality/assets"
}
```

There are no fallback defaults. A stage started without `MANIFEST` exits with an error rather
than guessing a batch — guessing is how a run silently overwrites a different batch's output.

`engine/paths.py` is the only module that builds paths. Moving a directory is a one-line
change there; nothing else hardcodes the layout, including the template (see below).

### ① `report_types/water_quality/analyze.py`
- Reads the source workbook; maps numeric participant numbers to internal IDs
  (`P0088T`, …) using `data/reference/Participant_Hornsense_ID_Map.xlsx` (shared across
  every report type, since it's the same participants).
- Groups rows by `(Participant_ID, Sample_date)` and splits each group into three sample
  locations: **Outdoor** (outdoor tap), **FF** (indoor first flush), **Filtered**.
- First pass computes community averages (with separate cohorts for chlorine- vs
  chloramine-disinfected systems); second pass builds the per-participant record.
- Applies pass/fail checks from `config.json` and resolves the virtual `Disinfectant`
  parameter to either `Chlorine_*` or `Chloramine_*` depending on the utility.
- Calls `finalize_record()` on every record — this is also what any mock-data builder for this
  type must call, so `records.json` is always render-ready regardless of where a record came
  from — and writes `build/water_quality/<batch>/records.json`.

### ② `report_types/water_quality/components/bar-gen.js`
Renders each parameter's horizontal scale bar (acceptable range in green, measured value as a
dot) in headless Chrome via Puppeteer and screenshots it to PNG. Spanish records get labels
translated from `report_types/water_quality/translations.xlsx`.

Checks that Chrome can actually launch before starting and exits non-zero if it cannot. Set
`DEBUG=1` to also dump each bar's HTML into `debug/`. This step is optional per the type
contract — a type with nothing to pre-render simply has no `components/` entry point, and the
engine skips this stage.

### ③ `engine/render.py`
1. Renders `report_types/<type>/templates/report.html` with Jinja2, then validates it against
   the template contract (`engine/validate.py`) — a missing `data-page` or a `data-toc-entry`
   with no matching anchor fails the whole run immediately, not once per record.
2. For Spanish reports, walks the DOM and substitutes text from the type's own
   `translations.xlsx` (`engine/translate.py`), calling the Google Translate API for anything
   missing and **caching new translations back into the spreadsheet**.
3. Drops pages whose content is empty and renumbers the table of contents
   (`engine/layout.py`), using the `data-page*` / `data-toc-*` attributes — never class names,
   since those are a per-type design choice.
4. Measures the real rendered height of each page with headless Chrome (Selenium) and
   generates fresh `@page` rules from scratch (`engine/layout.py` + `engine/pagination.py`).
5. Shells out to `weasyprint` to produce the PDF and moves it into `reports/<type>/<batch>/`,
   using the filename pattern from the type's own `config.json`.

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

1. **Report type** — which `report_types/<name>/` to use. Auto-selected while only one exists.
2. **Mode**
   - `1` — full pipeline over a real batch in `data/sources/<type>/`
   - `3` — template preview: renders one PDF from mock data into `reports/<type>/template/`,
     useful for iterating on a type's templates without touching real data. Mode 3 skips
     step ① and substitutes a fake record; steps ② and ③ are identical to a real run.
3. **Batch** — which input file under `data/sources/<type>/`. Its basename is the batch name
   and becomes the output subdirectory under `reports/<type>/`.

To run one stage by hand, point it at an existing manifest:

```bash
MANIFEST='build/water_quality/B8 Data/manifest.json' .venv/bin/python -m engine.render
```

(`-m` matters here — it puts the project root on `sys.path` so `engine`/`report_types` resolve
as packages; running the file by its path instead would not.)

---

## Layout

| Path | Purpose |
| --- | --- |
| `run_pipeline.py` | Interactive driver: choose type, mode, batch |
| `engine/` | Type-agnostic pipeline: paths, orchestration, render, translate, layout, pagination, validate — see `docs/multi-type-refactor.md` |
| `report_types/water_quality/` | Everything specific to this report type: `config.json`, `analyze.py`, `mock.py`, `components/`, `templates/`, `assets/`, `translations.xlsx` |
| `data/sources/<type>/` | Input workbooks for one type, one per batch |
| `data/reference/` | Lookup tables shared across every report type (currently just the participant ID map) |
| `reports/<type>/<batch>/` | Generated PDFs |
| `docs/multi-type-refactor.md` | The engine/type-package contracts and how this structure came to be |
| `archive/` | One-off scripts and reference files from earlier batches; not part of the pipeline |

### Generated, not tracked
`build/` holds everything the pipeline produces — records, bars and rendered HTML — and
`debug/` holds the optional bar dumps. Both are gitignored and safe to delete at any time.

`reports/` is also gitignored. The PDFs there are deliverables; the pipeline can regenerate
any batch from `data/sources/`, but back them up before re-running a batch you have already
distributed.

---

## Configuration

Everything tunable for this report type lives in `report_types/water_quality/config.json`. No
constants are duplicated in the Python or JavaScript sources, and nothing modifies the config
at runtime except the translation cache (see above).

| Key | Purpose |
| --- | --- |
| `parameterRanges` | Acceptable range and bar maximum per parameter |
| `parameterTypes` | Bar style and pass/fail logic per parameter (see table below) |
| `parameters.all` | Parameters shown in the report — used by the render stage and `bar-gen.js` |
| `parameters.measured` | What `analyze.py` computes: `all` plus the raw `Chlorine` and `Chloramine` columns that the virtual `Disinfectant` resolves to |
| `columnMap` | Internal parameter name → column name in the source workbook |
| `barDefaults` | Bar image size, and the axis maximum for unregulated (type 2) parameters |
| `files` | Names of the lookup files in this type's own directory, and the translation column headers |
| `waterUtilities` | Per-utility contact details, annual-report link and logo (path relative to this type's `assets/`) |
| `output` | PDF filename pattern and the English/Spanish prefix (`WATER`/`AGUA`) — read by `engine/render.py`, not hardcoded there |

### Parameter types

| Type | Meaning | Examples |
| --- | --- | --- |
| `0` | Banded scale with text labels, no pass/fail | `pH`, `Hardness` |
| `1` | Regulated `[min, max, bar_max]` range | `Lead`, `Nitrate`, `Chlorine` |
| `2` | Measured but unregulated — no range drawn | `Ammonia`, `Temperature` |
| `3` | Must be zero | `Bacteria` |

### Adding a parameter

1. In `report_types/water_quality/config.json`: add it to `parameterRanges`, `parameterTypes`,
   `parameters.all`, `parameters.measured` and `columnMap`.
2. In `report_types/water_quality/templates/report.html`: add one `parameter_box(...)` call and
   a table-of-contents entry.

---

## The report template

`report_types/water_quality/templates/report.html` renders the eight parameter sections
through a single macro rather than repeating the same markup once per parameter. Changing how
every parameter section looks is a change to `parameter_box` (or `parameter_box_binary`, used
only by Bacteria); adding a parameter is one more call.

The template never hardcodes how many `../` segments separate the rendered HTML from the files
it references. `engine/render.py` computes `assets_url` and `bars_url` and passes them in, and
`report.css` uses an `{{ASSETS}}` placeholder for the same reason. If you add an image
reference, use those variables rather than a relative path.

Each parameter's `<article>` wrapper is deliberately left inline, because the wrapper markup
differs between pages (some are inside `.chapter`, some are not) and those differences affect
the rendered width. See the comment block at the top of the template.

The engine finds its hooks in this template by `data-*` attribute
(`data-page`, `data-page-content`, `data-page-number`, `data-toc-entry`, `data-toc-page`), never
by class name — class names are this type's own design choice and are free to look however a
design calls for. See `docs/multi-type-refactor.md` section 5.2 for the full contract.

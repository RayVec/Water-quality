# WCWH Water Quality Reports

Generates personalized, bilingual (English / Spanish) drinking-water quality PDF reports for
participants in the Whole Communities–Whole Health (WCWH) study.

Given a batch of lab results in an Excel workbook, the pipeline produces one PDF per
participant/sample-date containing their measured values, how those values compare to
regulatory limits, and how they compare to the community average.

---

## Pipeline

```
data-source/<batch>.xlsx
        │
        │  ① data_analysis.py        pandas
        ▼
    data.json                        flat per-participant records
        │
        │  ② bar-gen.js              node + puppeteer + sharp
        ▼
images/output/<ID>/<date>/*.png      one scale bar per parameter × location
        │
        │  ③ report_gen.py           jinja2 + beautifulsoup + selenium + weasyprint
        ▼
reports/<batch>/WATER.<ID>.<YYYY.MM.DD>.pdf     (AGUA.* for Spanish)
```

`run_pipeline.py` drives all three steps and passes the selected batch between them via the
environment variables `DATA_SOURCE_PATH`, `DATA_JSON_PATH` and `OUTPUT_SUBDIR_NAME`.

### ① `data_analysis.py`
- Reads the source workbook; maps numeric participant numbers to internal IDs
  (`P0088T`, …) using `Participant_Hornsense_ID_Map.xlsx`.
- Groups rows by `(Participant_ID, Sample_date)` and splits each group into three sample
  locations: **Outdoor** (outdoor tap), **FF** (indoor first flush), **Filtered**.
- First pass computes community averages (with separate cohorts for chlorine- vs
  chloramine-disinfected systems); second pass builds the per-participant record.
- Applies pass/fail checks from `config.json` and resolves the virtual `Disinfectant`
  parameter to either `Chlorine_*` or `Chloramine_*` depending on the utility.
- Writes `data.json`.

### ② `bar-gen.js`
Renders each parameter's horizontal scale bar (acceptable range in green, measured value as a
dot) in headless Chrome via Puppeteer and screenshots it to PNG. Spanish records get labels
translated from `translations.xlsx`.

### ③ `report_gen.py`
1. Renders `reports/template/template.html` with Jinja2.
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
- Google Chrome — used by Selenium in step ③ (Puppeteer downloads its own Chromium)
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

> Note: `.venv/` is the working environment. The older `venv/` directory in this repo is stale
> and unused.

---

## Running

```bash
.venv/bin/python run_pipeline.py
```

You will be prompted for:

1. **Mode**
   - `1` — full pipeline over a real batch in `data-source/`
   - `3` — template preview: renders one PDF from mock data into `reports/template/`, useful
     for iterating on `template.html` / `report.css` without touching real data
2. **Data source** — which `.xlsx` in `data-source/` to process. The file's basename becomes the
   output subdirectory under `reports/`.

To run a single step by hand, set the same environment variables the driver would:

```bash
DATA_SOURCE_PATH=data-source/B8\ Data.xlsx OUTPUT_SUBDIR_NAME="B8 Data" .venv/bin/python data_analysis.py
```

---

## Layout

| Path | Purpose |
| --- | --- |
| `run_pipeline.py` | Interactive driver for the three steps |
| `data_analysis.py` | Step ① — Excel → `data.json` |
| `bar-gen.js` | Step ② — scale-bar PNGs |
| `report_gen.py` | Step ③ — HTML → PDF |
| `height_calculation.py` | Selenium helper that measures rendered element heights |
| `config.json` | Parameter limits, parameter types, water-utility directory |
| `translations.xlsx` | English→Spanish dictionary, read by both Python and Node; auto-extended |
| `reports/template/` | `template.html` + `report.css` — the report layout |
| `data-source/` | Input workbooks, one per batch |
| `reports/<batch>/` | Generated PDFs |
| `icons/`, `images/`, `inter/` | Static assets and the Inter font |
| `convert_b6_data.py`, `extract_out_of_range.py` | One-off helper scripts from earlier batches |

### Generated, not tracked
`temp/`, `debug/`, `images/output/` and `data.json` are rebuilt on every run and are gitignored.
Delete them freely.

---

## Parameter types

`config.json` assigns each parameter a type that controls both the pass/fail logic and how its
scale bar is drawn:

| Type | Meaning | Examples |
| --- | --- | --- |
| `0` | Banded scale with text labels, no pass/fail | `pH`, `Hardness` |
| `1` | Regulated `[min, max, bar_max]` range | `Lead`, `Nitrate`, `Chlorine` |
| `2` | Measured but unregulated — no range drawn | `Ammonia`, `Temperature` |
| `3` | Must be zero | `Bacteria` |

Adding a parameter means updating `parameterRanges`, `parameterTypes` and `parameters.all` in
`config.json`, adding a column mapping in `PARAMETER_COLUMN_MAP` in `data_analysis.py`, and
adding the corresponding section to `reports/template/template.html`.

"""Mock-data regression scenarios for the report pipeline.

Every scenario is a fully-formed record — same shape as run_pipeline.py's
template-preview mock — covering one combination of language, filtered
sample, disinfectant type and pass/fail axes. Feeding them through the real
pipeline (bar-gen.js + report_gen.py) and diffing the result against
tests/baseline/ is how every refactor step proves it hasn't changed the
deliverable. Deliberately synthetic: no real participant data ever goes
into tests/baseline/, which is committed to the repo.

Usage:
    .venv/bin/python tests/cases.py --capture-baseline
    .venv/bin/python tests/cases.py --verify
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import settings  # noqa: E402

BATCH = "test_scenarios"
BASELINE_DIR = Path(__file__).resolve().parent / "baseline"


def _metric_block(
    value_outdoor: Optional[float],
    value_ff: Optional[float],
    value_filtered: Optional[float],
    standard_outdoor: Optional[int],
    standard_ff: Optional[int],
    standard_filtered: Optional[int],
    avg_outdoor: Optional[float],
    avg_ff: Optional[float],
    avg_filtered: Optional[float],
    param_type: int,
) -> Dict[str, Any]:
    filtered_available = value_filtered is not None
    overall = 1 if all(v in (1, None) for v in [standard_outdoor, standard_ff, standard_filtered]) else 0
    return {
        "type": param_type,
        "Outdoor": value_outdoor,
        "Outdoor_Standard": standard_outdoor,
        "Outdoor_Average": avg_outdoor,
        "Outdoor_Evaluation": None,
        "FF": value_ff,
        "FF_Standard": standard_ff,
        "FF_Average": avg_ff,
        "FF_Evaluation": None,
        "Filtered_Available": filtered_available,
        "Filtered": value_filtered,
        "Filtered_Standard": standard_filtered if filtered_available else None,
        "Filtered_Average": avg_filtered if filtered_available else None,
        "Filtered_Evaluation": None,
        "Overall": overall,
    }


_SUFFIXES = [
    "Outdoor", "Outdoor_Standard", "Outdoor_Average", "Outdoor_Evaluation",
    "FF", "FF_Standard", "FF_Average", "FF_Evaluation",
    "Filtered_Available", "Filtered", "Filtered_Standard", "Filtered_Average", "Filtered_Evaluation",
    "Overall",
]


def _apply_metrics(record: Dict[str, Any], metrics: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    for parameter, block in metrics.items():
        record[f"{parameter}_type"] = block["type"]
        for suffix in _SUFFIXES:
            record[f"{parameter}_{suffix}"] = block[suffix]
    return record


def _base_record(
    participant_id: str,
    language: str,
    disinfectant_source: str,
    water_utility_name: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    utility_cfg = config["waterUtilities"][water_utility_name]
    return {
        "Participant_ID": participant_id,
        "Sample_date": "01/15/2025",
        "Language": language,
        "Water_System": water_utility_name,
        "Water_System_Report_Link": utility_cfg.get("annual_report", "https://example.org/report"),
        "Water_System_Phone_Number": utility_cfg.get("phone", "N/A"),
        "Water_System_Report_Evaluation": None,
        "Results": None,
        "Hornsense_ID": f"MOCK-{participant_id}",
        "Overall_Result": 1,
        "Disinfectant_Source": disinfectant_source,
    }


def _passing_metrics(filtered: bool) -> Dict[str, Dict[str, Any]]:
    f = (0.8, 0.02, 1.0, 0.05, 7.1, 0.05, 0.5, 0) if filtered else (None,) * 8
    return {
        "Disinfectant": _metric_block(1.2, 1.0, f[0], 1, 1, 1 if filtered else None, 1.3, 1.1, 0.9, 1),
        "Ammonia": _metric_block(0.08, 0.05, f[1], None, None, None, 0.07, 0.06, 0.03, 2),
        "Nitrate": _metric_block(1.6, 1.8, f[2], 1, 1, 1 if filtered else None, 1.5, 1.7, 1.1, 1),
        "Nitrite": _metric_block(0.2, 0.15, f[3], 1, 1, 1 if filtered else None, 0.18, 0.16, 0.06, 1),
        "pH": _metric_block(7.2, 7.4, f[4], None, None, None, 7.1, 7.3, 7.0, 0),
        "Turbidity": _metric_block(0.12, 0.09, f[5], 1, 1, 1 if filtered else None, 0.11, 0.1, 0.06, 1),
        "Lead": _metric_block(1.2, 2.8, f[6], 1, 1, 1 if filtered else None, 1.5, 2.1, 0.6, 1),
        "Bacteria": _metric_block(0, 0, f[7], 1, 1, 1 if filtered else None, 0, 0, 0, 3),
    }


def _failing_metrics() -> Dict[str, Dict[str, Any]]:
    return {
        "Disinfectant": _metric_block(0.05, 0.03, None, 0, 0, None, 1.3, 1.1, None, 1),
        "Ammonia": _metric_block(1.0, 0.9, None, None, None, None, 0.07, 0.06, None, 2),
        "Nitrate": _metric_block(20.0, 22.0, None, 0, 0, None, 1.5, 1.7, None, 1),
        "Nitrite": _metric_block(2.0, 1.9, None, 0, 0, None, 0.18, 0.16, None, 1),
        "pH": _metric_block(13.0, 12.8, None, None, None, None, 7.1, 7.3, None, 0),
        "Turbidity": _metric_block(3.0, 2.9, None, 0, 0, None, 0.11, 0.1, None, 1),
        "Lead": _metric_block(50.0, 55.0, None, 0, 0, None, 1.5, 2.1, None, 1),
        "Bacteria": _metric_block(3, 2, None, 0, 0, None, 0, 0, None, 3),
    }


def build_scenarios(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return {scenario_name: record} for every case the pipeline must handle."""
    scenarios: Dict[str, Dict[str, Any]] = {}

    record = _base_record("P9101T", "English", "Chlorine", "Austin Water", config)
    scenarios["en_chlorine_filtered_pass"] = _apply_metrics(record, _passing_metrics(filtered=True))

    record = _base_record("P9102T", "English", "Chloramine", "Goforth", config)
    record["Results"] = "Some parameters are outside the acceptable range."
    record["Overall_Result"] = 0
    scenarios["en_chloramine_nofiltered_fail"] = _apply_metrics(record, _failing_metrics())

    record = _base_record("P9103T", "Spanish", "Chlorine", "City of Kyle", config)
    scenarios["es_chlorine_filtered_pass"] = _apply_metrics(record, _passing_metrics(filtered=True))

    record = _base_record("P9104T", "Spanish", "Chloramine", "City of Manor", config)
    record["Overall_Result"] = 0
    metrics = _passing_metrics(filtered=False)
    metrics["Nitrate"] = _metric_block(12.0, 11.5, None, 0, 0, None, 1.5, 1.7, None, 1)
    scenarios["es_chloramine_nofiltered_mixed"] = _apply_metrics(record, metrics)

    record = _base_record("P9105T", "English", "Chlorine", "City of Killeen", config)
    record = _apply_metrics(record, _passing_metrics(filtered=False))
    record["Bacteria_Outdoor"] = "Sample not collected this round"
    record["Bacteria_FF"] = "Sample not collected this round"
    record["Bacteria_Filtered"] = "Sample not collected this round"
    record["Bacteria_Filtered_Available"] = False
    scenarios["en_missing_bacteria"] = record

    record = _base_record("P9106T", "English", "Chlorine", "County Line SUD", config)
    record["Results"] = "All tested parameters are outside the acceptable range."
    record["Overall_Result"] = 0
    scenarios["en_all_fail"] = _apply_metrics(record, _failing_metrics())

    return scenarios


def _scenario_output_paths(record: Dict[str, Any], manifest: Dict[str, str]) -> Tuple[Path, Path]:
    pid = record["Participant_ID"]
    month, day, year = record["Sample_date"].split("/")
    iso_date = f"{year}-{month}-{day}"
    lang_code = "es" if record["Language"].lower() == "spanish" else "en"
    prefix = "AGUA" if lang_code == "es" else "WATER"
    pdf_path = Path(manifest["reports"]) / f"{prefix}.{pid}.{year}.{month}.{day}.pdf"
    html_path = Path(manifest["work"]) / pid / f"{iso_date}_{lang_code}.html"
    return pdf_path, html_path


def run_scenarios() -> Dict[str, Tuple[Path, Path]]:
    """Write every scenario's record, run the real pipeline, return output paths."""
    config = settings.load_config()
    scenarios = build_scenarios(config)

    manifest_path = settings.write_manifest(BATCH)
    manifest = settings.resolve(BATCH)
    os.makedirs(os.path.dirname(manifest["records"]), exist_ok=True)
    with open(manifest["records"], "w", encoding="utf-8") as f:
        json.dump(list(scenarios.values()), f, indent=2, ensure_ascii=False)

    env = os.environ.copy()
    env[settings.ENV_VAR] = str(manifest_path)

    subprocess.run(["node", "bar-gen.js"], cwd=PROJECT_ROOT, env=env, check=True)
    subprocess.run([sys.executable, "report_gen.py"], cwd=PROJECT_ROOT, env=env, check=True)

    return {name: _scenario_output_paths(record, manifest) for name, record in scenarios.items()}


def capture_baseline() -> None:
    outputs = run_scenarios()
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    for name, (pdf_path, html_path) in outputs.items():
        if not pdf_path.exists():
            sys.exit(f"❌ {name}: expected PDF not found at {pdf_path}")
        if not html_path.exists():
            sys.exit(f"❌ {name}: expected HTML not found at {html_path}")
        shutil.copy(pdf_path, BASELINE_DIR / f"{name}.pdf")
        shutil.copy(html_path, BASELINE_DIR / f"{name}.html")
    print(f"✅ Captured baseline for {len(outputs)} scenarios into {BASELINE_DIR}")


def verify() -> None:
    import compare_dom
    import compare_pdf

    outputs = run_scenarios()
    failures = []
    for name, (pdf_path, html_path) in outputs.items():
        baseline_pdf = BASELINE_DIR / f"{name}.pdf"
        baseline_html = BASELINE_DIR / f"{name}.html"
        if not baseline_pdf.exists():
            failures.append(f"{name}: no baseline at {baseline_pdf} — run --capture-baseline first")
            continue

        pdf_diffs = compare_pdf.compare_pdfs(str(baseline_pdf), str(pdf_path))
        if pdf_diffs:
            failures.append(f"{name}: PDF differs — " + "; ".join(pdf_diffs))

        if baseline_html.exists():
            dom_diffs = compare_dom.compare_dom(str(baseline_html), str(html_path))
            if dom_diffs:
                print(f"ℹ️  {name}: DOM differs from baseline (informational):")
                print("\n".join(dom_diffs[:40]))

    if failures:
        print(f"\n❌ {len(failures)}/{len(outputs)} scenario(s) failed pixel comparison:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"\n✅ All {len(outputs)} scenarios pixel-identical to baseline.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture-baseline", action="store_true", help="Run scenarios and save output as the baseline.")
    group.add_argument("--verify", action="store_true", help="Run scenarios and diff against the baseline.")
    args = parser.parse_args()

    if args.capture_baseline:
        capture_baseline()
    else:
        verify()


if __name__ == "__main__":
    main()

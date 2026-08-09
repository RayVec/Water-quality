"""Record finishing + Excel batch -> records for the LENA report type.

No real LENA data source exists yet (see docs/lena-report-plan.md section 7).
analyze() reads a simulated source workbook whose columns are a best-effort
reverse-engineering of the Figma design. When the real data feed arrives,
only the column names read here need to change — the Record contract
(the fields finalize_record() produces) and the templates stay the same.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from engine import paths


def _age_in_months(birthday: str, recording_date: str) -> int:
    b = datetime.strptime(birthday, "%m/%d/%Y")
    r = datetime.strptime(recording_date, "%m/%d/%Y")
    months = (r.year - b.year) * 12 + (r.month - b.month)
    if r.day < b.day:
        months -= 1
    return max(months, 0)


def _percentile_tier(percentile: float, bands: Dict[str, Any]) -> Tuple[str, str]:
    for key, band in bands.items():
        if band["min"] <= percentile <= band["max"]:
            return key, band["label"]
    # Percentiles are 1-99 by definition; fall back to the lowest band rather
    # than raise, since a malformed source value shouldn't take down a run.
    lowest_key = min(bands, key=lambda k: bands[k]["min"])
    return lowest_key, bands[lowest_key]["label"]


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _bucket(tier_key: str) -> str:
    """Collapse the 4 percentile bands to 3 for interpretation sentences —
    the design only ever phrases Low Average/High Average as "about the
    same", reserving "fewer/more" language for the Low/High extremes.
    """
    if tier_key == "low":
        return "low"
    if tier_key == "high":
        return "high"
    return "mid"


def _vocalizations_sentence(bucket: str) -> str:
    if bucket == "low":
        return "Your child vocalizes less than most children their age."
    if bucket == "high":
        return "Your child vocalizes more than most children their age."
    return "Your child vocalizes about the same as most children their age."


def _turns_sentence(bucket: str) -> str:
    if bucket == "low":
        return "Your child has fewer conversational turns than most children their age."
    if bucket == "high":
        return "Your child has more conversational turns than most children their age."
    return "Your child has about the same number of conversational turns as most children their age."


def _productivity_sentence(bucket: str) -> str:
    if bucket == "low":
        return "Your child uses fewer utterances within conversations than most children their age."
    if bucket == "high":
        return "Your child uses more utterances within conversations than most children their age."
    return "Your child's utterances within conversations are about the same as most children their age."


def finalize_record(record: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a raw combined record into a render-ready one — see
    report_types/water_quality/analyze.py for why this is a separate step
    every mock/real record path funnels through.
    """
    bands = config["percentileBands"]

    record["id"] = str(record["Participant_ID"])
    record["date"] = datetime.strptime(record["Recording_Date"], "%m/%d/%Y").strftime("%Y-%m-%d")
    record["language"] = record.get("Language", "English")

    record["child_name"] = record["Child_Name"]
    record["birthday"] = record["Birthday"]
    record["recording_date_display"] = record["Recording_Date"]
    record["age_at_recording"] = f"{_age_in_months(record['Birthday'], record['Recording_Date'])} months"
    record["recording_duration_hours"] = record["Recording_Duration_Hours"]

    record["child_vocalizations_count"] = record["Child_Vocalizations"]
    record["child_vocalizations_display"] = f"{record['Child_Vocalizations']:,}"
    record["conversational_turns_count"] = record["Conversational_Turns"]
    record["conversational_turns_display"] = f"{record['Conversational_Turns']:,}"
    record["adult_words_display"] = f"{record['Adult_Words']:,}"
    record["most_active_time_vocalizations"] = record["Most_Active_Time_Vocalizations"]
    record["most_active_time_turns"] = record["Most_Active_Time_Turns"]

    vtier_key, vtier_label = _percentile_tier(record["Child_Vocalizations_Percentile"], bands)
    ttier_key, ttier_label = _percentile_tier(record["Conversational_Turns_Percentile"], bands)
    ptier_key, ptier_label = _percentile_tier(record["Vocal_Productivity_Percentile"], bands)

    record["vocalizations_percentile"] = record["Child_Vocalizations_Percentile"]
    record["vocalizations_percentile_display"] = f"{_ordinal(record['Child_Vocalizations_Percentile'])} percentile"
    record["vocalizations_percentile_key"] = vtier_key
    record["vocalizations_percentile_label"] = vtier_label
    record["vocalizations_interpretation"] = _vocalizations_sentence(_bucket(vtier_key))

    record["turns_percentile"] = record["Conversational_Turns_Percentile"]
    record["turns_percentile_display"] = f"{_ordinal(record['Conversational_Turns_Percentile'])} percentile"
    record["turns_percentile_key"] = ttier_key
    record["turns_percentile_label"] = ttier_label
    record["turns_interpretation"] = _turns_sentence(_bucket(ttier_key))

    record["productivity_percentile"] = record["Vocal_Productivity_Percentile"]
    record["productivity_percentile_display"] = f"{_ordinal(record['Vocal_Productivity_Percentile'])} percentile"
    record["productivity_percentile_key"] = ptier_key
    record["productivity_percentile_label"] = ptier_label
    record["productivity_interpretation"] = _productivity_sentence(_bucket(ptier_key))

    record["audio_environment"] = {
        "Noise": record["AudioEnv_Noise_Pct"],
        "SilenceBackground": record["AudioEnv_Silence_Pct"],
        "Overlap": record["AudioEnv_Overlap_Pct"],
        "TvElectronic": record["AudioEnv_TV_Pct"],
        "Speech": record["AudioEnv_Speech_Pct"],
        "DistantNoise": record["AudioEnv_DistantNoise_Pct"],
    }

    # Config-driven, not per-record: baked in here (not read by the template
    # from config directly) because the engine only ever hands templates the
    # record dict — see report_types/water_quality's water_utility for the
    # same pattern.
    record["resource_directory"] = config["resourceDirectory"]
    record["contact_section"] = config["contactSection"]
    record["audio_categories"] = config["audioEnvironment"]["categories"]
    record["percentile_bands"] = bands

    return record


def analyze(source_path: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Simulated-source batch -> render-ready records (see module docstring)."""
    if not Path(source_path).exists():
        sys.exit(f"❌ Error: Input workbook not found: {source_path}")

    df = pd.read_excel(source_path)
    df.columns = df.columns.str.strip()

    records = []
    for _, row in df.iterrows():
        record = {col: (None if pd.isna(row[col]) else row[col]) for col in df.columns}
        records.append(finalize_record(record, config))
    return records


def main() -> None:
    manifest = paths.load_manifest()
    config = paths.load_config(manifest["type"])
    records = analyze(manifest["source"], config)

    import json
    import os

    json_file_path = manifest["records"]
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
    with open(json_file_path, "w") as f:
        json.dump(records, f, indent=4, default=str)
    print(f"Combined records have been exported to {json_file_path}")


if __name__ == "__main__":
    main()

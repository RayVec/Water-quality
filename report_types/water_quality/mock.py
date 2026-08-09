"""Mock data for previewing a report design without waiting on real data.

Used by run_pipeline.py's template-preview mode, and reused as-is by the
test harness (tests/cases.py) for its own scenario variations. Every mock
record is built in the same raw shape analyze.py's analyze() produces
internally, then passed through the same finalize_record() so it is
render-ready exactly the way a real batch's records are.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .analyze import finalize_record


def metric_block(
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
    "Outdoor",
    "Outdoor_Standard",
    "Outdoor_Average",
    "Outdoor_Evaluation",
    "FF",
    "FF_Standard",
    "FF_Average",
    "FF_Evaluation",
    "Filtered_Available",
    "Filtered",
    "Filtered_Standard",
    "Filtered_Average",
    "Filtered_Evaluation",
    "Overall",
]


def build_template_record(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build one fake record that matches report_gen/bar-gen expected fields."""
    today = datetime.now().strftime("%m/%d/%Y")
    water_utility_name = "Austin Water"
    utility_cfg = config["waterUtilities"][water_utility_name]

    record = {
        "Participant_ID": "P9999T",
        "Sample_date": today,
        "Language": "English",
        "Water_System": water_utility_name,
        "Water_System_Report_Link": utility_cfg.get("annual_report", "https://example.org/report"),
        "Water_System_Phone_Number": utility_cfg.get("phone", "N/A"),
        "Water_System_Report_Evaluation": "This is mock data for a template preview only.",
        "Results": "Standard",
        "Hornsense_ID": "MOCK-0001",
        "Overall_Result": 1,
        "Disinfectant_Source": "Chlorine",
    }

    metrics = {
        "Disinfectant": metric_block(1.2, 1.0, None, 1, 1, None, 1.3, 1.1, None, 1),
        "Ammonia": metric_block(0.08, 0.05, None, None, None, None, 0.07, 0.06, None, 2),
        "Nitrate": metric_block(1.6, 1.8, None, 1, 1, None, 1.5, 1.7, None, 1),
        "Nitrite": metric_block(0.2, 0.15, None, 1, 1, None, 0.18, 0.16, None, 1),
        "pH": metric_block(8.9, 8.5, None, None, None, None, 8.8, 8.6, None, 0),
        "Turbidity": metric_block(0.12, 0.09, None, 1, 1, None, 0.11, 0.1, None, 1),
        "Lead": metric_block(1.2, 2.8, None, 1, 1, None, 1.5, 2.1, None, 1),
        "Bacteria": metric_block(0, 0, None, 1, 1, None, 0, 0, None, 3),
    }

    for parameter, block in metrics.items():
        record[f"{parameter}_type"] = block["type"]
        for suffix in _SUFFIXES:
            record[f"{parameter}_{suffix}"] = block[suffix]

    return record


def mock(config: Dict[str, Any]) -> Dict[str, Any]:
    """One render-ready fake record, for previewing a report design with no real data."""
    return finalize_record(build_template_record(config), config)

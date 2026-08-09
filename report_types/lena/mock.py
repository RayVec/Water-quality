"""Mock data for previewing the LENA report design without a real batch.

See report_types/water_quality/mock.py for why this exists and how it's
used (run_pipeline.py's template-preview mode, tests/cases.py scenarios).
"""
from __future__ import annotations

from typing import Any, Dict

from .analyze import finalize_record


def build_template_record(config: Dict[str, Any]) -> Dict[str, Any]:
    """One fake raw record, same shape analyze()'s Excel rows produce."""
    return {
        "Participant_ID": "L0142",
        "Child_Name": "Hazel",
        "Birthday": "05/04/2023",
        "Recording_Date": "04/12/2025",
        "Language": "English",
        "Recording_Duration_Hours": 24,
        "Adult_Words": 17761,
        "Child_Vocalizations": 1429,
        "Conversational_Turns": 389,
        "Most_Active_Time_Vocalizations": "12:00-01:00 PM",
        "Most_Active_Time_Turns": "04:00-05:00 PM",
        "Child_Vocalizations_Percentile": 26,
        "Conversational_Turns_Percentile": 35,
        "Vocal_Productivity_Percentile": 10,
        "AudioEnv_Noise_Pct": 68,
        "AudioEnv_Silence_Pct": 40,
        "AudioEnv_Overlap_Pct": 33,
        "AudioEnv_TV_Pct": 30,
        "AudioEnv_Speech_Pct": 28,
        "AudioEnv_DistantNoise_Pct": 29,
    }


def mock(config: Dict[str, Any]) -> Dict[str, Any]:
    """One render-ready fake record, for previewing the report with no real data."""
    return finalize_record(build_template_record(config), config)

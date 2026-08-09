"""Single source of truth for every path the pipeline uses.

A run is identified by two things: the report type and the batch name.
Every other path is derived from them here, so no other module builds
paths by hand and no module carries its own fallback default.

The three stages receive that batch through one environment variable
pointing at a manifest file:

    MANIFEST='build/water_quality/B8 Data/manifest.json' python report_types/water_quality/analyze.py

The manifest is plain JSON so components scripts (which may not be Python)
read the same file the Python stages do, rather than re-deriving the paths
in another language.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Directory layout -------------------------------------------------------
# These constants are the only place the layout is written down. Moving a
# directory means editing one line here.
#
#   data/reference/          lookup tables shared across every report type
#   data/sources/<type>/     input batches for one type, one file per batch,
#                            extension chosen by that type (not assumed xlsx)
#   report_types/<type>/     that type's config, analyze/mock code, templates,
#                            assets and components — everything engine/ doesn't
#                            need to know about
#   build/<type>/<batch>/    everything generated; safe to delete at any time
#   reports/<type>/<batch>/  the delivered PDFs
DATA_DIR = PROJECT_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
SOURCES_DIR = DATA_DIR / "sources"
TYPES_DIR = PROJECT_ROOT / "report_types"
BUILD_DIR = PROJECT_ROOT / "build"
REPORTS_DIR = PROJECT_ROOT / "reports"

ENV_VAR = "MANIFEST"


def _type_dir(type_name: str) -> Path:
    return TYPES_DIR / type_name


def load_config(type_name: str) -> Dict[str, Any]:
    """Load one type's own config.json. There is no shared/global config."""
    config_file = _type_dir(type_name) / "config.json"
    with open(config_file, encoding="utf-8") as f:
        return json.load(f)


def _find_source_file(type_name: str, batch: str) -> Optional[Path]:
    """The one file under sources/<type>/ whose stem is `batch`, whatever its
    extension — the engine doesn't assume Excel, that's up to the type's
    analyze().
    """
    matches = sorted((SOURCES_DIR / type_name).glob(f"{batch}.*"))
    return matches[0] if matches else None


def resolve(type_name: str, batch: str) -> Dict[str, str]:
    """Derive every path for one run. The only place this mapping exists.

    'work' is deliberately kept at a fixed depth per type. The rendered HTML
    sits in work/<participant>/ and reaches assets with a relative path
    computed at render time, so adding a directory level there would need
    that computation to change too, not just this mapping. Bars carry the
    batch instead, which is what actually needed isolating: they used to be
    written to a shared path, so two batches holding the same participant and
    date overwrote each other.
    """
    source_file = _find_source_file(type_name, batch)
    return {
        "type": type_name,
        "batch": batch,
        "source": str(source_file) if source_file else "",
        "records": str(BUILD_DIR / type_name / batch / "records.json"),
        "bars": str(BUILD_DIR / type_name / batch / "bars"),
        "work": str(BUILD_DIR / type_name / "work"),
        "reports": str(REPORTS_DIR / type_name / batch),
        "type_dir": str(_type_dir(type_name)),
        "templates": str(_type_dir(type_name) / "templates"),
        "assets": str(_type_dir(type_name) / "assets"),
    }


def write_manifest(type_name: str, batch: str) -> Path:
    """Resolve a run and persist it where every stage can read it."""
    manifest = resolve(type_name, batch)
    path = BUILD_DIR / type_name / batch / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return path


def load_manifest() -> Dict[str, str]:
    """Read the manifest named by $MANIFEST.

    Deliberately has no fallback. Previously each stage guessed a different
    default when its environment variable was missing, so running one stage by
    hand could silently read one batch and write over another.
    """
    raw = os.environ.get(ENV_VAR)
    if not raw:
        sys.exit(
            f"❌ {ENV_VAR} is not set.\n"
            f"   Run the pipeline through run_pipeline.py, or point it at a run:\n"
            f"       {ENV_VAR}='build/<type>/<batch>/manifest.json' python {Path(sys.argv[0]).name}"
        )
    path = Path(raw)
    if not path.is_file():
        sys.exit(f"❌ Manifest not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def available_types() -> list[str]:
    """Type names that have a config.json, sorted."""
    if not TYPES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in TYPES_DIR.iterdir()
        if p.is_dir() and (p / "config.json").is_file()
    )


def available_batches(type_name: str) -> list[str]:
    """Batch names that have an input file under sources/<type>/, sorted."""
    type_sources_dir = SOURCES_DIR / type_name
    if not type_sources_dir.is_dir():
        return []
    return sorted(p.stem for p in type_sources_dir.iterdir() if p.is_file())

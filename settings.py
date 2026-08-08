"""Single source of truth for every path the pipeline uses.

A run is identified by exactly one thing: the batch name. Every other path is
derived from it here, so no other module builds paths by hand and no module
carries its own fallback default.

The three stages receive that batch through one environment variable pointing
at a manifest file:

    MANIFEST='build/B8 Data/manifest.json' python report_gen.py

The manifest is plain JSON so bar-gen.js reads the same file the Python stages
do, rather than re-deriving the paths in JavaScript.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent

# --- Directory layout -------------------------------------------------------
# These constants are the only place the layout is written down. Moving a
# directory means editing one line here.
#
#   data/sources/     input workbooks, one per batch
#   data/reference/   lookup tables that outlive any single batch
#   templates/        report.html + report.css
#   assets/           icons, images and fonts referenced by the report
#   build/            everything generated; safe to delete at any time
#   reports/<batch>/  the delivered PDFs
DATA_DIR = PROJECT_ROOT / "data"
SOURCES_DIR = DATA_DIR / "sources"
REFERENCE_DIR = DATA_DIR / "reference"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
ASSETS_DIR = PROJECT_ROOT / "assets"
BUILD_DIR = PROJECT_ROOT / "build"
REPORTS_DIR = PROJECT_ROOT / "reports"
CONFIG_FILE = PROJECT_ROOT / "config.json"

ENV_VAR = "MANIFEST"


def resolve(batch: str) -> Dict[str, str]:
    """Derive every path for one batch. The only place this mapping exists.

    'work' is deliberately kept at a fixed depth. The rendered HTML sits in
    work/<participant>/ and reaches the shared assets with '../../assets/...',
    so adding a directory level there would silently break every icon, font and
    background image in the report. Bars carry the batch instead, which is what
    actually needed isolating: they used to be written to a shared path, so two
    batches holding the same participant and date overwrote each other.
    """
    return {
        "batch": batch,
        "source": str(SOURCES_DIR / f"{batch}.xlsx"),
        "records": str(BUILD_DIR / batch / "records.json"),
        "bars": str(BUILD_DIR / batch / "bars"),
        "work": str(BUILD_DIR / "work"),
        "reports": str(REPORTS_DIR / batch),
    }


def write_manifest(batch: str) -> Path:
    """Resolve a batch and persist it where the three stages can read it."""
    manifest = resolve(batch)
    path = BUILD_DIR / batch / "manifest.json"
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
            f"   Run the pipeline through run_pipeline.py, or point it at a batch:\n"
            f"       {ENV_VAR}='build/<batch>/manifest.json' python {Path(sys.argv[0]).name}"
        )
    path = Path(raw)
    if not path.is_file():
        sys.exit(f"❌ Manifest not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> Dict[str, Any]:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def available_batches() -> list[str]:
    """Batch names that have an input workbook, sorted."""
    if not SOURCES_DIR.is_dir():
        return []
    return sorted(p.stem for p in SOURCES_DIR.glob("*.xlsx"))

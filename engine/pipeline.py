"""Orchestrates one run: analyze -> components (optional) -> render.

Each stage is a separate process, so a type's components step can be in any
language (today's water_quality type shells out to Node). run_pipeline.py is
the interactive CLI that decides type/batch/mode and calls into this.
"""
from __future__ import annotations

import os
import subprocess
import sys


def run_command(command: str, description: str, env=None) -> bool:
    """Run a command and wait for it to complete, streaming its output."""
    print(f"\n{'='*50}")
    print(f"STARTING: {description}")
    print(f"{'='*50}")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=True,
            universal_newlines=True,
            env=env,
        )

        for line in process.stdout:
            print(line.strip())

        return_code = process.wait()

        if return_code == 0:
            print(f"\n✅ {description} completed successfully")
            return True
        else:
            print(f"\n❌ {description} failed with error code {return_code}")
            return False

    except Exception as e:
        print(f"\n❌ Failed to execute {description}: {str(e)}")
        return False


def run_analyze(type_name: str, env: dict) -> bool:
    # Run as a module (`-m`), not a bare file path: analyze.py does
    # `from engine import paths`, which needs the project root on sys.path.
    # `-m` puts the interpreter's current directory there; a direct file path
    # would put analyze.py's own directory there instead, and `engine` would
    # not be importable.
    return run_command(
        f'"{sys.executable}" -m report_types.{type_name}.analyze', "Data Analysis", env=env
    )


def run_components(type_dir: str, env: dict) -> bool:
    """Components are optional (contract 5.3): a type with nothing to
    pre-render just doesn't have this entry point, and this step no-ops.
    """
    components_entry = os.path.join(type_dir, "components", "bar-gen.js")
    if not os.path.exists(components_entry):
        print("\nℹ️  No components entry point for this type — skipping.")
        return True
    return run_command(f'node "{components_entry}"', "Component Generation", env=env)


def run_render(env: dict) -> bool:
    return run_command(f'"{sys.executable}" -m engine.render', "Report Generation", env=env)

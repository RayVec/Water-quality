#!/usr/bin/env python3
"""Interactive driver: choose a report type, a mode, and (for the real
pipeline) a batch, then run analyze -> components -> render through
engine.pipeline.
"""
import importlib
import json
import os
import sys
import time

from engine import paths, pipeline


def choose_type():
    """Prompt the user to select a report type (one report_types/<name>/)."""
    types = paths.available_types()

    if not types:
        print(f"❌ No report types found under {paths.TYPES_DIR}")
        sys.exit(1)

    if len(types) == 1:
        print(f"✅ Automatically selected type: {types[0]}")
        return types[0]

    print("请选择报告类型:")
    for idx, name in enumerate(types, start=1):
        print(f"  {idx}. {name}")

    while True:
        choice = input("Enter the number of the type to use: ").strip()
        if not choice.isdigit():
            print("Please enter a valid number from the list.")
            continue

        index = int(choice)
        if index < 1 or index > len(types):
            print("Selection out of range. Try again.")
            continue

        print(f"✅ Selected type: {types[index - 1]}")
        return types[index - 1]


def choose_batch(type_name):
    """Prompt the user to select a batch (one input file under sources/<type>/)."""
    batches = paths.available_batches(type_name)

    if not batches:
        print(f"❌ No input files found in {paths.SOURCES_DIR / type_name}")
        sys.exit(1)

    if len(batches) == 1:
        print(f"✅ Automatically selected batch: {batches[0]}")
        return batches[0]

    print("Available batches:")
    for idx, name in enumerate(batches, start=1):
        print(f"  {idx}. {name}")

    while True:
        choice = input("Enter the number of the batch to use: ").strip()
        if not choice.isdigit():
            print("Please enter a valid number from the list.")
            continue

        index = int(choice)
        if index < 1 or index > len(batches):
            print("Selection out of range. Try again.")
            continue

        print(f"✅ Selected batch: {batches[index - 1]}")
        return batches[index - 1]


def choose_pipeline_mode():
    """Prompt the user to select pipeline mode."""
    print("请选择要执行的流程:")
    print("  1. 完整流程（真实数据：data/sources 下的输入文件 -> 分析 -> 组件 -> 报告）")
    print("  3. 模板流程（假数据 + 当前模板 -> reports/<type>/template）")
    while True:
        choice = input("请输入选项编号 (1 或 3): ").strip()
        if choice in {"1", "3"}:
            return choice
        print("请输入有效选项：1 或 3。")


def _load_type_module(type_name: str, module_name: str):
    """Import a module from inside a type's own package by name — the
    engine doesn't hardcode `import mock` for one type, since a different
    type's module lives under a different package path. A real package
    import (not a synthetic one off a bare file path) so the module's own
    relative imports, e.g. mock.py's `from .analyze import ...`, resolve.
    """
    return importlib.import_module(f"report_types.{type_name}.{module_name}")


def write_template_records(manifest, type_name):
    """Mode 3: skip the analysis stage and write one fake record instead."""
    config = paths.load_config(type_name)
    mock = _load_type_module(type_name, "mock")
    records_path = manifest["records"]
    os.makedirs(os.path.dirname(records_path), exist_ok=True)
    with open(records_path, "w", encoding="utf-8") as f:
        json.dump([mock.mock(config)], f, indent=2, ensure_ascii=False)


def main():
    # Define the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print(f"Starting data processing pipeline in {project_dir}")

    type_name = choose_type()
    mode = choose_pipeline_mode()
    batch = "template" if mode == "3" else choose_batch(type_name)

    # Type + batch in, every path out. Downstream stages get a single
    # environment variable pointing at the resulting manifest.
    manifest_path = paths.write_manifest(type_name, batch)
    manifest = paths.resolve(type_name, batch)
    env = os.environ.copy()
    env[paths.ENV_VAR] = str(manifest_path)

    print(f"Type:     {type_name}")
    print(f"Batch:    {batch}")
    print(f"Manifest: {manifest_path}")
    print(f"Reports:  {manifest['reports']}")

    # Stage 1: build the records. Real batches read the source file through
    # the type's own analyze.py; template mode substitutes mock data so the
    # design can be previewed without any real data.
    if mode == "3":
        write_template_records(manifest, type_name)
    elif not pipeline.run_analyze(type_name, env):
        print("Pipeline stopped due to error in data analysis step")
        sys.exit(1)

    # Stage 2: components (optional — a type with nothing to pre-render skips this)
    if not pipeline.run_components(manifest["type_dir"], env):
        print("Pipeline stopped due to error in component generation step")
        sys.exit(1)

    # Stage 3: render
    if not pipeline.run_render(env):
        print("Pipeline stopped due to error in report generation step")
        sys.exit(1)

    print(f"\n🎉 Pipeline finished. Reports are in {manifest['reports']}")


if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")

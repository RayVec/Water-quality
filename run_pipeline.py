#!/usr/bin/env python3
import subprocess
import os
import time
import sys
import json

import settings
import mock

def run_command(command, description, env=None):
    """Run a command and wait for it to complete"""
    print(f"\n{'='*50}")
    print(f"STARTING: {description}")
    print(f"{'='*50}")
    
    try:
        # Run the command and capture output
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout
            text=True,
            bufsize=1,  # Line buffered
            shell=True,
            universal_newlines=True,
            env=env
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(line.strip())
        
        # Get the return code
        return_code = process.wait()
        
        # Check if command was successful
        if return_code == 0:
            print(f"\n✅ {description} completed successfully")
            return True
        else:
            print(f"\n❌ {description} failed with error code {return_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Failed to execute {description}: {str(e)}")
        return False

def choose_batch():
    """Prompt the user to select a batch (one .xlsx in data/sources/)."""
    batches = settings.available_batches()

    if not batches:
        print(f"❌ No .xlsx files found in {settings.SOURCES_DIR}")
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
    print("  1. 完整流程（真实数据：data/sources 下的 Excel -> 分析 -> 刻度条 -> 报告）")
    print("  3. 模板流程（假数据 + 当前模板 -> reports/template）")
    while True:
        choice = input("请输入选项编号 (1 或 3): ").strip()
        if choice in {"1", "3"}:
            return choice
        print("请输入有效选项：1 或 3。")

def write_template_records(manifest):
    """Mode 3: skip the analysis stage and write one fake record instead."""
    config = settings.load_config()
    records_path = manifest["records"]
    os.makedirs(os.path.dirname(records_path), exist_ok=True)
    with open(records_path, "w", encoding="utf-8") as f:
        json.dump([mock.mock(config)], f, indent=2, ensure_ascii=False)


def main():
    # Define the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print(f"Starting data processing pipeline in {project_dir}")

    mode = choose_pipeline_mode()
    batch = "template" if mode == "3" else choose_batch()

    # One batch name in, every path out. Downstream stages get a single
    # environment variable pointing at the resulting manifest.
    manifest_path = settings.write_manifest(batch)
    manifest = settings.resolve(batch)
    env = os.environ.copy()
    env[settings.ENV_VAR] = str(manifest_path)

    print(f"Batch:    {batch}")
    print(f"Manifest: {manifest_path}")
    print(f"Reports:  {manifest['reports']}")

    # Step 1: build the records. Real batches read the workbook; the template
    # mode substitutes mock data so template.html can be previewed offline.
    if mode == "3":
        write_template_records(manifest)
    elif not run_command(f"\"{sys.executable}\" data_analysis.py", "Data Analysis", env=env):
        print("Pipeline stopped due to error in data analysis step")
        sys.exit(1)

    # Step 2: Run bar-gen.js
    if not run_command("node bar-gen.js", "Bar Chart Generation", env=env):
        print("Pipeline stopped due to error in bar chart generation step")
        sys.exit(1)

    # Step 3: Run report_gen.py
    if not run_command(f"\"{sys.executable}\" report_gen.py", "Report Generation", env=env):
        print("Pipeline stopped due to error in report generation step")
        sys.exit(1)

    print(f"\n🎉 Pipeline finished. Reports are in {manifest['reports']}")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")
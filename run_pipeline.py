#!/usr/bin/env python3
import subprocess
import os
import time
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional

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

def choose_data_source(data_directory):
    """Prompt the user to select a data-source Excel file."""
    if not os.path.isdir(data_directory):
        print(f"❌ Data source directory not found: {data_directory}")
        sys.exit(1)

    data_files = [f for f in os.listdir(data_directory) if f.lower().endswith('.xlsx')]
    data_files.sort()

    if not data_files:
        print(f"❌ No .xlsx files found in {data_directory}")
        sys.exit(1)

    if len(data_files) == 1:
        selected = data_files[0]
        print(f"✅ Automatically selected data source: {selected}")
        return os.path.join(data_directory, selected), selected

    print("Available data sources:")
    for idx, filename in enumerate(data_files, start=1):
        print(f"  {idx}. {filename}")

    while True:
        choice = input("Enter the number of the data source to use: ").strip()
        if not choice.isdigit():
            print("Please enter a valid number from the list.")
            continue

        index = int(choice)
        if index < 1 or index > len(data_files):
            print("Selection out of range. Try again.")
            continue

        selected = data_files[index - 1]
        print(f"✅ Selected data source: {selected}")
        return os.path.join(data_directory, selected), selected

def choose_pipeline_mode():
    """Prompt the user to select pipeline mode."""
    print("请选择要执行的流程:")
    print("  1. 完整流程（真实数据：data-source Excel -> data_analysis -> bar-gen -> report_gen）")
    print("  3. 模板流程（假数据 + 当前模板 -> reports/template）")
    while True:
        choice = input("请输入选项编号 (1 或 3): ").strip()
        if choice in {"1", "3"}:
            return choice
        print("请输入有效选项：1 或 3。")

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

def build_template_record(config):
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
        "Disinfectant": _metric_block(1.2, 1.0, None, 1, 1, None, 1.3, 1.1, None, 1),
        "Ammonia": _metric_block(0.08, 0.05, None, None, None, None, 0.07, 0.06, None, 2),
        "Nitrate": _metric_block(1.6, 1.8, None, 1, 1, None, 1.5, 1.7, None, 1),
        "Nitrite": _metric_block(0.2, 0.15, None, 1, 1, None, 0.18, 0.16, None, 1),
        "pH": _metric_block(8.9, 8.5, None, None, None, None, 8.8, 8.6, None, 0),
        "Turbidity": _metric_block(0.12, 0.09, None, 1, 1, None, 0.11, 0.1, None, 1),
        "Lead": _metric_block(1.2, 2.8, None, 1, 1, None, 1.5, 2.1, None, 1),
        "Bacteria": _metric_block(0, 0, None, 1, 1, None, 0, 0, None, 3),
    }

    for parameter, block in metrics.items():
        record[f"{parameter}_type"] = block["type"]
        for suffix in [
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
        ]:
            record[f"{parameter}_{suffix}"] = block[suffix]

    return record

def run_template_pipeline(project_dir):
    """Generate one template PDF with fake data to reports/template."""
    config_path = os.path.join(project_dir, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    temp_template_dir = os.path.join(project_dir, "temp", "template")
    os.makedirs(temp_template_dir, exist_ok=True)
    data_json_path = os.path.join(temp_template_dir, "template_data.json")

    template_record = build_template_record(config)
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump([template_record], f, indent=2, ensure_ascii=False)

    env = os.environ.copy()
    env["DATA_JSON_PATH"] = data_json_path
    env["OUTPUT_SUBDIR_NAME"] = "template"

    print(f"Template data JSON: {data_json_path}")
    print("Reports will be stored under: reports/template")

    if not run_command("node bar-gen.js", "Bar Chart Generation (Template)", env=env):
        print("Template pipeline stopped due to error in bar chart generation step")
        sys.exit(1)

    if not run_command(f"\"{sys.executable}\" report_gen.py", "Report Generation (Template)", env=env):
        print("Template pipeline stopped due to error in report generation step")
        sys.exit(1)

    print("\n🎉 Template PDF generated successfully at reports/template")

def main():
    # Define the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    print(f"Starting data processing pipeline in {project_dir}")

    mode = choose_pipeline_mode()

    if mode == "3":
        run_template_pipeline(project_dir)
        return

    data_directory = os.path.join(project_dir, 'data-source')
    data_source_path, data_source_filename = choose_data_source(data_directory)

    # Export selection via environment variables for downstream scripts
    output_subdir = os.path.splitext(data_source_filename)[0]
    env = os.environ.copy()
    env['DATA_SOURCE_PATH'] = data_source_path
    env['OUTPUT_SUBDIR_NAME'] = output_subdir

    print(f"Data source path: {data_source_path}")
    print(f"Reports will be stored under: reports/{output_subdir}")
    
    # Step 1: Run data_analysis.py (it will find its input via config.json)
    if not run_command(f"\"{sys.executable}\" data_analysis.py", "Data Analysis", env=env):
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
    
    print("\n🎉 Complete data processing pipeline executed successfully!")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")
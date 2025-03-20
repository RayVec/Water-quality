#!/usr/bin/env python3
import subprocess
import os
import time
import sys

def run_command(command, description):
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
            universal_newlines=True
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

def main():
    # Define the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    # Define input file path
    input_file_path = os.path.join(project_dir, 'B6_Data_Converted.csv')
    
    print(f"Starting data processing pipeline in {project_dir}")
    
    # Step 1: Run data_analysis.py with file path argument
    if not run_command(f"python3 data_analysis.py {input_file_path}", "Data Analysis"):
        print("Pipeline stopped due to error in data analysis step")
        sys.exit(1)
    
    # Step 2: Run bar-gen.js
    if not run_command("node bar-gen.js", "Bar Chart Generation"):
        print("Pipeline stopped due to error in bar chart generation step")
        sys.exit(1)
    
    # Step 3: Run report_gen.py
    if not run_command("python3 report_gen.py", "Report Generation"):
        print("Pipeline stopped due to error in report generation step")
        sys.exit(1)
    
    print("\n🎉 Complete data processing pipeline executed successfully!")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")
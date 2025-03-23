import os
from jinja2 import Environment, FileSystemLoader
import subprocess
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def gen_report(output_file_name):
    logging.info(f"Generating PDF report: {output_file_name.replace('.html', '.pdf')}")
    command = "weasyprint "+output_file_name+" "+output_file_name.replace(".html", ".pdf")

    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        logging.info("PDF generation completed successfully")
        if result.stdout or result.stderr:
            logging.debug(f"Process output: {result.stdout}\n{result.stderr}")
    else:
        logging.error(f"Failed to generate PDF: {result.stderr}")

def gen_template(record):
    id = str(record["Participant ID"])
    date = record['date']   
    
    logging.info(f"Processing template for Participant ID: {id}, Date: {date}")
    
    env = Environment(loader=FileSystemLoader('./'))
    
    if not os.path.exists('./reports/'+id):
        logging.info(f"Creating new directory for participant: {id}")
        os.makedirs('./reports/'+id)

    template = env.get_template('./reports/template/template.html')
    output = template.render(record)
    output_file_name = "./reports/"+id+"/"+date+".html"
    
    os.makedirs(os.path.dirname(output_file_name), exist_ok=True)
    
    logging.info(f"Writing HTML report: {output_file_name}")
    with open(output_file_name, 'w') as f:
        f.write(output)
        f.flush()
    gen_report(output_file_name)

file_path = 'data.json'  # Replace with your file path

# Load the shared configuration for water utilities
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    water_utilities = config.get('waterUtilities', {})  # Get water utilities from config
    parameters = config['parameters']['all']  # Load parameter list from config

with open(file_path, 'r') as file:
    records = json.load(file)  # Load the JSON data as a Python list
    # direct convert the record["Sample_date"] to yyyy-mm-dd
    for record in records:
        record['date'] = datetime.strptime(str(record["Sample_date"]), '%m/%d/%Y').strftime('%Y-%m-%d')
        record["Participant_ID"] = record["Participant ID"]
        
        # Add a list to track which parameters to display
        record["display_parameters"] = []
        
        for parameter in parameters:  # Use parameters from config instead of hardcoded list
            # Check if the parameter has non-null values for any location
            has_values = False
            for location in ["Outdoor", "FF", "AF"]:
                if record.get(f"{parameter}_{location}") is not None:
                    has_values = True
                    break
            
            # Only include parameter in display list if it has values
            if has_values:
                record["display_parameters"].append(parameter)
            
            # if parameter's outdoor, af and ff standard are all 1, then set the parameter_standard to 1, or set it to be 0
            if record[parameter+'_Outdoor_Standard'] in [1,None] and record[parameter+'_FF_Standard'] in [1,None] and record[parameter+'_AF_Standard'] in [1,None]:
                record[parameter+'_Standard'] = 1
            else:
                record[parameter+'_Standard'] = 0

        water_utility=record["Water System"]
        if water_utility in water_utilities:
            record["water_utility"] = water_utilities[water_utility]
        gen_template(record)
    # for record in records:
    #     print(record)
    #     gen_template(record)
# except Exception as e:
#     print(e)

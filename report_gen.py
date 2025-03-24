import os
from jinja2 import Environment, FileSystemLoader
import subprocess
import json
from datetime import datetime
import logging
import shutil
from height_calculation import calculate_rendered_height

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
    
    # Create custom CSS file with dynamically calculated heights
    generate_custom_css(output_file_name, id)
    
    gen_report(output_file_name)

def generate_custom_css(html_file_path, participant_id):
    """
    Generate a custom CSS file with dynamically calculated page heights
    
    Args:
        html_file_path (str): Path to the HTML file to analyze
        participant_id (str): Participant ID (for directory structure)
    """
    logging.info(f"Generating custom CSS with dynamic page heights for {html_file_path}")
    
    # Read the template CSS file
    template_css_path = "./reports/template/report.css"
    css_content = ""
    with open(template_css_path, 'r', encoding='utf-8') as css_file:
        css_content = css_file.read()
    
    # List of pages to measure
    pages_to_measure = ["page2", "page3", "page4", "page5", "page6", "page7", "page8", "page9", "page10"]
    
    # Calculate height for each page
    import re
    for page_id in pages_to_measure:
        try:
            height = calculate_rendered_height(html_file_path, css_content, page_id)
            height = height+2
            # Add some padding to ensure content fits (adjust as needed)
            # height_with_padding = height + 50
            
            logging.info(f"Calculated height for {page_id}: {height}px ")
            
            # Replace height in @page rule
            css_content = re.sub(
                r'(@page\s+' + page_id + r'\s*\{\s*height\s*:\s*)[^;]+;', 
                r'\g<1>' + str(height) + 'px;', 
                css_content
            )
            
            # If #pageX has a height property, update it
            if re.search(r'#' + page_id + r'\s*\{[^\}]*height\s*:', css_content):
                css_content = re.sub(
                    r'(#' + page_id + r'\s*\{[^\}]*height\s*:\s*)[^;]+;', 
                    r'\g<1>' + str(height) + 'px;', 
                    css_content
                )
            # If #pageX exists but doesn't have a height property, add it
            elif re.search(r'#' + page_id + r'\s*\{', css_content):
                css_content = re.sub(
                    r'(#' + page_id + r'\s*\{)([^\}]*)\}', 
                    r'\g<1>\g<2>  height: ' + str(height) + 'px;\n}', 
                    css_content
                )
            # If #pageX doesn't exist, create it
            else:
                css_content += f"\n#{page_id} {{\n  height: {height}px;\n  page: {page_id};\n}}"
            
        except Exception as e:
            logging.error(f"Error calculating height for {page_id}: {str(e)}")
    
    # Write the updated CSS to the participant's directory
    participant_css_path = os.path.dirname(html_file_path) + "/report.css"
    with open(participant_css_path, 'w', encoding='utf-8') as css_file:
        css_file.write(css_content)
    
    logging.info(f"Custom CSS file created at {participant_css_path}")

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

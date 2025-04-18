import os
from jinja2 import Environment, FileSystemLoader
import subprocess
import json
from datetime import datetime
import logging
import shutil
from height_calculation import calculate_rendered_height
import numbers # Import the numbers module
import time
from translations import SPANISH_TRANSLATIONS # Import the dictionary
from bs4 import BeautifulSoup, NavigableString, Comment # Import BeautifulSoup AND Comment
from googletrans import Translator # Import Translator
import asyncio # Import asyncio
import re # Import regex for stripping tags
from typing import List, Dict, Any, Optional, Set, Union # Import types for annotations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def is_valid_numeric_value(value: Any) -> bool:
    """Check if a value is a number (int, float, or numeric string)."""
    if value is None:
        return False
    if isinstance(value, numbers.Number): # Catches int, float
        return True
    if isinstance(value, str):
        # Check if string represents a number (allowing for decimals)
        # Remove leading/trailing whitespace before checking
        return value.strip().replace('.', '', 1).isdigit()
    return False # Not a number or numeric string

def _process_record_parameters(record: Dict[str, Any], all_parameters_config: List[str]) -> Dict[str, Any]:
    """Processes parameter-related data for a single record."""
    
    # Add a list to track which parameters to display
    record["display_parameters"] = []
    
    for parameter in all_parameters_config:
        # Check if the parameter has AT LEAST ONE valid numeric value for any location
        is_displayed = False
        for location in ["Outdoor", "FF", "AF"]: # Consider making locations configurable if needed
            value = record.get(f"{parameter}_{location}")
            # Use the helper function to check for numeric or None
            if is_valid_numeric_value(value) or value is None:
                 is_displayed = True
                 break # Found a displayable value, no need to check other locations
        
        # Only include parameter in display list if it has valid data or is None
        if is_displayed:
            record["display_parameters"].append(parameter)
        
        # Calculate overall standard
        # Check if standards are 1 or None (or missing)
        outdoor_standard = record.get(f'{parameter}_Outdoor_Standard')
        ff_standard = record.get(f'{parameter}_FF_Standard')
        af_standard = record.get(f'{parameter}_AF_Standard')

        if (outdoor_standard in [1, None]) and \
           (ff_standard in [1, None]) and \
           (af_standard in [1, None]):
            record[f'{parameter}_Standard'] = 1
        else:
            record[f'{parameter}_Standard'] = 0 # At least one location is out of standard (and not None)

    # Calculate how many parameters meet the overall standard
    in_range_count = 0
    # Use count of parameters actually having data for this record
    total_parameters_count = len(record["display_parameters"]) 
    for parameter in record["display_parameters"]: # Iterate through parameters with data only
        # Check if the overall standard for this parameter is 1 
        # (standard calculation already handles None implicitly)
        if record.get(f'{parameter}_Standard') == 1:
             in_range_count += 1
    
    # Add count and total to the record for template rendering
    record['in_range_count'] = in_range_count
    record['total_parameters_count'] = total_parameters_count

    # Identify parameters not tested or without valid data for this specific record
    record['not_tested_parameters'] = []
    tested_params_set = set(record["display_parameters"])
    all_params_set = set(all_parameters_config) 
    
    missing_params = list(all_params_set - tested_params_set)
    
    for param in missing_params:
        reason = "No data available for this parameter in the sample."
        # Check original fields for explanatory text (if it's a string and not numeric)
        outdoor_val = record.get(f'{param}_Outdoor')
        ff_val = record.get(f'{param}_FF')
        af_val = record.get(f'{param}_AF')
        
        # Prioritize explanatory text if available
        if isinstance(outdoor_val, str) and not is_valid_numeric_value(outdoor_val):
            reason = outdoor_val
        elif isinstance(ff_val, str) and not is_valid_numeric_value(ff_val):
            reason = ff_val
        elif isinstance(af_val, str) and not is_valid_numeric_value(af_val):
            reason = af_val

        record['not_tested_parameters'].append({
            'name': param,
            'reason': reason
        })
        
    return record # Return the modified record

def gen_report(output_file_name: str, participant_id: str, date: str, language_code: str) -> None:
    # Define the paths
    temp_folder: str = os.path.dirname(output_file_name)  # This is in the temp folder
    reports_folder: str = f"./reports/{participant_id}"
    
    # Create reports directory if it doesn't exist
    os.makedirs(reports_folder, exist_ok=True)
    
    # Final PDF path in reports folder
    final_pdf_path = f"{reports_folder}/{date}.pdf"
    temp_pdf_path = output_file_name.replace(".html", ".pdf")
    
    logging.info(f"Generating PDF report: {temp_pdf_path}")
    command = f"weasyprint {output_file_name} {temp_pdf_path}"

    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        logging.info("PDF generation completed successfully")
        if result.stdout or result.stderr:
            logging.debug(f"Process output: {result.stdout}\n{result.stderr}")
        
        # Move the PDF to the reports folder
        logging.info(f"Moving PDF from {temp_pdf_path} to {final_pdf_path}")
        shutil.move(temp_pdf_path, final_pdf_path)
    else:
        logging.error(f"Failed to generate PDF: {result.stderr}")

# Async helper function for batch translation
async def fetch_translations_async(texts_to_translate: List[str]) -> Dict[str, str]:
    """Translates a list of texts using googletrans API asynchronously."""
    api_translations: Dict[str, str] = {}
    if not texts_to_translate:
        return api_translations
        
    logging.info(f"Calling Google Translate API for {len(texts_to_translate)} unique texts...")
    try:
        # Use async with as per documentation
        async with Translator() as translator:
            results = await translator.translate(texts_to_translate, dest='es', src='en')
        
        # Process results (handling potential list/single object return)
        if isinstance(results, list):
            for i, result in enumerate(results):
                if result and result.text:
                    original = texts_to_translate[i] # Get corresponding original text
                    # Basic tag stripping from API result as a safeguard
                    plain_text_translation = re.sub(r'<[^>]+>', '', result.text) 
                    api_translations[original] = plain_text_translation
                else:
                    logging.warning(f"Google Translate API returned no text for: '{texts_to_translate[i]}'")
        elif results and results.text: # Handle single result case if only one text was passed
             plain_text_translation = re.sub(r'<[^>]+>', '', results.text)
             api_translations[texts_to_translate[0]] = plain_text_translation
        else:
            logging.warning(f"Google Translate API returned unexpected result type or no text.")
            
        logging.info(f"Received {len(api_translations)} translations from API.")
        
    except Exception as e:
        logging.error(f"Google Translate API error during batch call: {e}", exc_info=True)
        # Return empty dict on error, could implement retries etc.
        api_translations = {}
        
    return api_translations

# Rename function again based on user preference
def create_report_pdf(record: Dict[str, Any]) -> None:
    id: str = str(record["Participant_ID"])
    date: str = record['date']
    language: str = record.get("Language", "English") # Default to English if missing
    language_code: str = 'es' if language.lower() == 'spanish' else 'en'
    
    logging.info(f"Processing template for Participant ID: {id}, Date: {date}, Language: {language} ({language_code})" )
    
    # Set up Jinja2 environment to load templates from the current directory
    env = Environment(loader=FileSystemLoader('./'))
    
    # Define and create temporary directory for this report
    temp_dir = f"./temp/{id}"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
    
    # Ensure the final report directory exists
    if not os.path.exists(f'./reports/{id}'):
        os.makedirs(f'./reports/{id}', exist_ok=True)

    # Load the base HTML template
    template_path = './reports/template/template.html'
    logging.info(f"Loading base template: {template_path}")
        
    template = env.get_template(template_path)
    # Render the template with the record data (initially in English)
    rendered_html = template.render(record)
    # final_html_content will hold the potentially translated HTML
    final_html_content = rendered_html # Default to original

    if language_code == 'es':
        logging.info("Applying Spanish translation...")
        try:
            # 1. Parse HTML ONCE
            soup: BeautifulSoup = BeautifulSoup(rendered_html, 'html.parser')
            
            # 2. Find unique texts needing API translation
            texts_to_translate_set: Set[str] = set()
            all_text_nodes = soup.find_all(string=True)
            
            for node in all_text_nodes:
                # Skip script/style/comment content etc.
                if node.parent.name in ['script', 'style', '[document]', 'head', 'title', 'meta'] or isinstance(node, Comment):
                    continue
                original_text = node.strip()
                # Check if non-empty and not already in the dictionary
                if original_text and original_text not in SPANISH_TRANSLATIONS:
                    texts_to_translate_set.add(original_text)
            
            logging.info(f"Found {len(texts_to_translate_set)} unique texts not in local dictionary.")
            
            # 3. Fetch API translations if needed
            api_translations: Dict[str, str] = {}
            if texts_to_translate_set:
                 api_translations = asyncio.run(fetch_translations_async(list(texts_to_translate_set)))
            
            # 4. Combine dictionaries (API results first, then dictionary overrides/adds)
            combined_translations: Dict[str, str] = api_translations.copy()
            combined_translations.update(SPANISH_TRANSLATIONS) 
            
            # 5. Apply translations by modifying the original soup object
            replaced_count = 0
            for node in all_text_nodes: # Iterate through the nodes found earlier
                # Skip script/style/comment content etc.
                if node.parent.name in ['script', 'style', '[document]', 'head', 'title', 'meta'] or isinstance(node, Comment):
                    continue
                original_text = node.strip()
                if not original_text:
                    continue
                
                translated_text = combined_translations.get(original_text)
                
                # Replace if translation exists and is different from original
                if translated_text and translated_text != original_text:
                    # Ensure the translation is treated as plain text
                    # (The API fetch function already strips tags, but dictionary values might not)
                    plain_translation = re.sub(r'<[^>]+>', '', translated_text)
                    node.replace_with(NavigableString(plain_translation))
                    replaced_count += 1
            
            logging.info(f"Applied {replaced_count} translations to HTML structure.")
            
            # 6. Get the final HTML from the modified soup
            final_html_content = str(soup)
            
        except Exception as e:
            logging.error(f"Error during Spanish translation processing for {id}, {date}: {e}", exc_info=True)
            # Fallback to untranslated HTML on error
            final_html_content = rendered_html # Ensure it falls back correctly
    
    # --- Write HTML and Generate PDF --- 
    output_file_name = f"{temp_dir}/{date}_{language_code}.html"
    logging.info(f"Writing final HTML report to temp directory: {output_file_name}")
    with open(output_file_name, 'w', encoding='utf-8') as f: # Specify encoding
        f.write(final_html_content)
        f.flush()
    
    # Generate CSS based on the final HTML structure
    generate_custom_css(output_file_name, id)
    # Generate report from the final HTML file
    gen_report(output_file_name, id, date, language_code)

def generate_custom_css(html_file_path: str, participant_id: str) -> None:
    """
    Generate a custom CSS file with dynamically calculated page heights
    
    Args:
        html_file_path (str): Path to the HTML file to analyze
        participant_id (str): Participant ID (for directory structure)
    """
    logging.info(f"Generating custom CSS with dynamic page heights for {html_file_path}")
    
    # Path to CSS in the temp folder
    temp_folder = os.path.dirname(html_file_path)
    participant_css_path = os.path.join(temp_folder, "report.css")
    
    if os.path.exists(participant_css_path):
        logging.info(f"Deleting existing CSS file: {participant_css_path}")
        os.remove(participant_css_path)
    
    # Read the template CSS file
    template_css_path = "./reports/template/report.css"
    css_content = ""
    with open(template_css_path, 'r', encoding='utf-8') as css_file:
        css_content = css_file.read()
    
    # List of pages to measure
    pages_to_measure = ["page2", "page3", "page4", "page5", "page6", "page7", "page8", "page9", "page10"]
    
    # Calculate heights for all pages at once
    import re
    try:
        # Use the new, optimized function that calculates all heights in a single browser session
        from height_calculation import calculate_rendered_heights
        page_heights = calculate_rendered_heights(html_file_path, css_content, pages_to_measure)
        
        for page_id, height in page_heights.items():
            if height is None:
                logging.error(f"Failed to calculate height for {page_id}")
                continue
                
            # Add 2px padding
            height = height + 2
            logging.info(f"Calculated height for {page_id}: {height}px")
            
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
        logging.error(f"Error calculating heights: {str(e)}")
    
    # Write the updated CSS to the participant's temp directory
    with open(participant_css_path, 'w', encoding='utf-8') as css_file:
        css_file.write(css_content)
    
    logging.info(f"Custom CSS file created at {participant_css_path}")
    

# Main script execution remains synchronous
def main() -> None:
    file_path: str = 'data.json'
    if not os.path.exists('./temp'):
        os.makedirs('./temp')
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
        water_utilities = config.get('waterUtilities', {}) 
        parameters = config['parameters']['all'] 
    with open(file_path, 'r') as file:
        records: List[Dict[str, Any]] = json.load(file) 
        processed_records: int = 0
        total_records: int = len(records)
        start_time = time.time()
        for i, record in enumerate(records):
            try:
                # Preprocessing
                record['date'] = datetime.strptime(str(record.get("Sample_date", "")), '%m/%d/%Y').strftime('%Y-%m-%d')
                record = _process_record_parameters(record, parameters)
                water_utility_key = record.get("Water_System")
                if water_utility_key and water_utility_key in water_utilities:
                    record["water_utility"] = water_utilities[water_utility_key]
                else:
                    record["water_utility"] = None 
                    logging.warning(f"Water utility '{water_utility_key}' not found for {record.get('Participant_ID')}")
                
                # Call the renamed function
                create_report_pdf(record)
                processed_records += 1
                
                if (i + 1) % 10 == 0 or (i + 1) == total_records:
                     elapsed_time = time.time() - start_time
                     logging.info(f"Processed {i + 1}/{total_records} records in {elapsed_time:.2f} seconds.")
            except Exception as e:
                 logging.error(f"Failed to process record {i+1} (ID: {record.get('Participant_ID', 'N/A')}): {e}", exc_info=True)
        
        end_time = time.time()
        logging.info(f"Finished processing. Successful reports: {processed_records}/{total_records}")
        logging.info(f"Total execution time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()

# Optional cleanup
# shutil.rmtree('./temp', ignore_errors=True)

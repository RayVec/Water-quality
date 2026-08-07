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
# from translations import SPANISH_TRANSLATIONS # No longer importing directly
from bs4 import BeautifulSoup, NavigableString, Comment # Import BeautifulSoup AND Comment
from googletrans import Translator # Import Translator
import asyncio # Import asyncio
import re # Import regex for stripping tags
from typing import List, Dict, Any, Optional, Set, Union # Import types for annotations
# import pprint # No longer needed for saving
import pandas as pd # Import pandas for Excel handling

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Translation Handling --- 
TRANSLATIONS_FILE = "translations.xlsx"
ENGLISH_COL = "English"
SPANISH_COL = "Spanish"

def _load_translations_from_excel() -> Dict[str, str]:
    """Loads translations from the Excel file into a dictionary."""
    translations_dict: Dict[str, str] = {}
    if not os.path.exists(TRANSLATIONS_FILE):
        logging.warning(f"Translations file '{TRANSLATIONS_FILE}' not found. Starting with empty dictionary.")
        return translations_dict

    try:
        logging.info(f"Loading translations from {TRANSLATIONS_FILE}...")
        df = pd.read_excel(TRANSLATIONS_FILE)
        
        # Check if required columns exist
        if ENGLISH_COL not in df.columns or SPANISH_COL not in df.columns:
            logging.error(f"Translations file '{TRANSLATIONS_FILE}' must contain '{ENGLISH_COL}' and '{SPANISH_COL}' columns.")
            return translations_dict # Return empty if columns are wrong

        # Fill NaN values (empty cells) with empty strings before creating dict
        df = df.fillna('')

        # Populate dictionary, ensuring both key and value are strings
        for index, row in df.iterrows():
            key = str(row[ENGLISH_COL])
            value = str(row[SPANISH_COL])
            if key: # Only add if key is not empty
                translations_dict[key] = value
                
        logging.info(f"Successfully loaded {len(translations_dict)} translations.")
    except Exception as e:
        logging.error(f"Failed to load translations from '{TRANSLATIONS_FILE}': {e}", exc_info=True)
        # Return empty dict on error to avoid crashing
        translations_dict = {} 
        
    return translations_dict

def _save_translations() -> None:
    """Saves the current state of SPANISH_TRANSLATIONS back to the Excel file."""
    logging.info(f"Saving updated translations to {TRANSLATIONS_FILE}...")
    try:
        # Convert the dictionary back to a DataFrame
        # Ensure keys/values end up in the correct columns
        items = list(SPANISH_TRANSLATIONS.items())
        df = pd.DataFrame(items, columns=[ENGLISH_COL, SPANISH_COL])
        
        # Sort by English column for consistency
        df = df.sort_values(by=ENGLISH_COL)
        
        # Save to Excel, overwriting the file and not writing the index
        df.to_excel(TRANSLATIONS_FILE, index=False, engine='openpyxl') 
        logging.info(f"Successfully saved {len(df)} translations to {TRANSLATIONS_FILE}.")
    except Exception as e:
        logging.error(f"Failed to save translations to {TRANSLATIONS_FILE}: {e}", exc_info=True)

# Load translations at startup
SPANISH_TRANSLATIONS: Dict[str, str] = _load_translations_from_excel()
# --- End Translation Handling ---

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
    
    locations = ["Outdoor", "FF", "Filtered"]

    for parameter in all_parameters_config:
        # Check if the parameter has AT LEAST ONE valid numeric value for any location
        is_displayed = False
        for location in locations:
            value = record.get(f"{parameter}_{location}")
            # Use the helper function to check for numeric or None
            if is_valid_numeric_value(value) or value is None:
                 is_displayed = True
                 break # Found a displayable value, no need to check other locations

        # Only include parameter in display list if it has valid data or is None
        if is_displayed:
            record["display_parameters"].append(parameter)

        # Calculate overall standard only across available locations
        standard_values = []
        for location in locations:
            standard_val = record.get(f'{parameter}_{location}_Standard')
            available_flag = record.get(f'{parameter}_{location}_Available')
            if available_flag is None or available_flag is True:
                standard_values.append(standard_val)

        if all(val in (1, None) for val in standard_values):
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
        filtered_val = record.get(f'{param}_Filtered')
        
        # Prioritize explanatory text if available
        if isinstance(outdoor_val, str) and not is_valid_numeric_value(outdoor_val):
            reason = outdoor_val
        elif isinstance(ff_val, str) and not is_valid_numeric_value(ff_val):
            reason = ff_val
        elif isinstance(filtered_val, str) and not is_valid_numeric_value(filtered_val):
            reason = filtered_val

        record['not_tested_parameters'].append({
            'name': param,
            'reason': reason
        })
        
    return record # Return the modified record

def gen_report(output_file_name: str, participant_id: str, final_pdf_filename: str, language_code: str, final_report_dir: str) -> None:
    # Define the paths
    temp_folder: str = os.path.dirname(output_file_name)  # This is in the temp folder
    reports_folder: str = final_report_dir 
    
    # Ensure the final report directory exists (might be redundant if created in main, but safe)
    os.makedirs(reports_folder, exist_ok=True)
    
    # Final PDF path uses the specific directory and filename
    final_pdf_path = os.path.join(reports_folder, final_pdf_filename)
    # Define the temporary PDF path (created in the temp folder)
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
def create_report_pdf(record: Dict[str, Any], final_report_dir: str) -> None:
    id: str = str(record["Participant_ID"])
    date: str = record['date'] # Original date in YYYY-MM-DD
    language: str = record.get("Language", "English") # Default to English if missing
    language_code: str = 'es' if language.lower() == 'spanish' else 'en'
    
    logging.info(f"Processing template for Participant ID: {id}, Date: {date}, Language: {language} ({language_code})" )
    
    # Set up Jinja2 environment to load templates from the current directory
    env = Environment(loader=FileSystemLoader('./'))
    
    # Add dynamic metadata for templates
    record['latest_annual_report_year'] = datetime.now().year - 1

    # Define and create temporary directory for this report
    temp_dir = f"./temp/{id}"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
    
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
                # Check if non-empty, not the literal string "None", and not already in the dictionary
                if original_text and original_text != "None" and original_text not in SPANISH_TRANSLATIONS:
                    texts_to_translate_set.add(original_text)
            
            logging.info(f"Found {len(texts_to_translate_set)} unique texts not in local dictionary.")
            
            # 3. Fetch API translations if needed
            api_translations: Dict[str, str] = {}
            if texts_to_translate_set:
                 api_translations = asyncio.run(fetch_translations_async(list(texts_to_translate_set)))
                 
                 # --- Caching Step ---
                 if api_translations: # Check if we got new translations
                    logging.info(f"Updating local translation dictionary with {len(api_translations)} new entries...")
                    # Update the global dictionary in memory
                    SPANISH_TRANSLATIONS.update(api_translations) 
                    # Save the updated dictionary back to the file (now Excel)
                    _save_translations() 
                 # --- End Caching Step ---
            
            # 4. Combine dictionaries (API results already added to SPANISH_TRANSLATIONS)
            #    We now use the potentially updated global dictionary directly
            combined_translations: Dict[str, str] = SPANISH_TRANSLATIONS.copy() 
            
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
    
    # Remove empty pages and keep table of contents in sync
    final_html_content = remove_empty_pages_and_update_toc(final_html_content)

    # --- Write HTML and Generate PDF --- 
    # Define temporary HTML filename
    output_file_name = f"{temp_dir}/{date}_{language_code}.html"
    logging.info(f"Writing final HTML report to temp directory: {output_file_name}")
    with open(output_file_name, 'w', encoding='utf-8') as f: # Specify encoding
        f.write(final_html_content)
        f.flush()
    
    # Generate CSS based on the final HTML structure
    generate_custom_css(output_file_name, id)
    
    # --- Construct final PDF filename --- 
    report_type = "AGUA" if language_code == 'es' else "WATER"
    formatted_date = date.replace('-', '.') # Change YYYY-MM-DD to YYYY.MM.DD
    final_pdf_filename = f"{report_type}.{id}.{formatted_date}.pdf"
    
    # Generate report from the final HTML file, passing the desired final filename and directory
    gen_report(output_file_name, id, final_pdf_filename, language_code, final_report_dir)

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
    
    # Determine the pages to measure dynamically based on the rendered HTML
    pages_to_measure = []
    try:
        with open(html_file_path, 'r', encoding='utf-8') as html_file:
            soup = BeautifulSoup(html_file, 'html.parser')

        seen_ids = set()
        for element in soup.find_all(id=True):
            element_id = element.get('id')
            if element_id and (element_id == 'toc' or element_id.startswith('page')):
                if element_id not in seen_ids:
                    pages_to_measure.append(element_id)
                    seen_ids.add(element_id)

        if not pages_to_measure:
            raise ValueError("No page sections with ids 'toc' or starting with 'page' were found.")

    except Exception as exc:
        logging.error(f"Failed to detect pages dynamically for {html_file_path}: {exc}")
        pages_to_measure = ["toc", "page2", "page3", "page4", "page5", "page6", "page7", "page8", "page9", "page10"]
    
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
            height = height - 30
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
    

# --- HTML post-processing helpers ---
def _content_has_meaningful_data(content_node: Optional[BeautifulSoup]) -> bool:
    """Determine if a content node contains meaningful text or media."""
    if not content_node:
        return False

    text = content_node.get_text(strip=True)
    if text:
        return True

    # Check for media or other non-textual content
    media_tags = ["img", "svg", "figure", "table", "video", "canvas", "iframe", "object"]
    if content_node.find(media_tags):
        return True

    return False


def remove_empty_pages_and_update_toc(html_content: str) -> str:
    """Remove empty page articles and update page numbering and table of contents."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove empty page articles (skip toc)
    for article in list(soup.find_all('article')):
        article_id = article.get('id')
        if not article_id or article_id == 'toc':
            continue

        content = article.find('div', class_='content')
        if not _content_has_meaningful_data(content):
            logging.info(f"Removing empty page section: {article_id}")
            article.decompose()

    # Rebuild page ordering and id-to-page mapping
    id_to_page: Dict[str, int] = {}
    page_number = 1
    for article in soup.find_all('article'):
        article_id = article.get('id')
        if not article_id:
            continue

        # Map the article's own id to the page number
        id_to_page[article_id] = page_number

        # Update header/footer page numbers
        for number_span in article.select('div.header span.number'):
            number_span.string = str(page_number)

        # Map all element ids within this article to the page number
        for element_with_id in article.find_all(id=True):
            id_to_page[element_with_id['id']] = page_number

        page_number += 1

    # Update table of contents entries based on the new mapping
    toc_article = soup.find('article', id='toc')
    if toc_article:
        headings = toc_article.select('.headings .heading1, .headings .heading2')
        for heading in list(headings):
            link = heading.select_one('.title a')
            page_div = heading.select_one('.page')

            if not link or not page_div:
                continue

            target = link.get('href', '')
            if not target.startswith('#'):
                continue

            target_id = target[1:]
            page_for_target = id_to_page.get(target_id)

            if page_for_target is None:
                logging.info(f"Removing TOC entry without target: {target_id}")
                heading.decompose()
            else:
                page_div.string = str(page_for_target)

    return str(soup)


# Main script execution remains synchronous
def main() -> None:
    file_path: str = os.environ.get('DATA_JSON_PATH', 'data.json')
    if not os.path.exists('./temp'):
        os.makedirs('./temp')
    
    # Load configuration
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
        water_utilities = config.get('waterUtilities', {}) 
        parameters = config['parameters']['all']
        # Determine output subdirectory (allow environment override)
        output_subdir_name = os.environ.get('OUTPUT_SUBDIR_NAME')
        if not output_subdir_name:
            output_subdir_name = config.get('output_report_subdirectory', 'b6')
        
    # Define and create the final output directory
    final_report_dir = os.path.join(".", "reports", output_subdir_name)
    os.makedirs(final_report_dir, exist_ok=True)
    logging.info(f"Final reports will be saved to: {final_report_dir}")

    # Load data records
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
                
                # Call the renamed function, passing the final report directory
                create_report_pdf(record, final_report_dir)
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

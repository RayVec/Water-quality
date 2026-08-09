"""Jinja render -> translate -> layout (empty-page removal, @page generation)
-> WeasyPrint -> move into reports/.

This is the engine's render stage: it knows the Record contract (id / date /
language) and the template attribute contract (docs/multi-type-refactor.md,
sections 5.1-5.2), and nothing else about any particular report type.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from engine import paths
from engine import translate
from engine import layout
from engine.validate import validate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def gen_report(output_file_name: str, participant_id: str, final_pdf_filename: str, language_code: str, final_report_dir: str) -> None:
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


def _output_filename(record: Dict[str, Any], language: str, language_code: str, config: Dict[str, Any]) -> str:
    """Filename rules come from the type's own config (contract 5.3) — not
    hardcoded WATER/AGUA in the engine.
    """
    output_cfg = config.get('output', {})
    prefix_map = output_cfg.get('prefix', {})
    prefix = prefix_map.get(language, language_code.upper())
    date_format = output_cfg.get('dateFormat', '%Y.%m.%d')
    formatted_date = datetime.strptime(record['date'], '%Y-%m-%d').strftime(date_format)
    pattern = output_cfg.get('filename', '{prefix}.{id}.{date}.pdf')
    return pattern.format(prefix=prefix, id=record['id'], date=formatted_date)


def create_report_pdf(record: Dict[str, Any], manifest: Dict[str, str], config: Dict[str, Any]) -> None:
    id: str = record["id"]
    date: str = record['date']  # Original date in YYYY-MM-DD
    language: str = record.get("language", "English")  # Default to English if missing
    language_code: str = 'es' if language.lower() == 'spanish' else 'en'
    final_report_dir: str = manifest['reports']

    logging.info(f"Processing template for id: {id}, Date: {date}, Language: {language} ({language_code})")

    # Set up Jinja2 environment to load templates from the type's own template directory
    env = Environment(loader=FileSystemLoader(manifest['templates']))

    # Define and create temporary directory for this report
    temp_dir = os.path.join(manifest['work'], id)
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)

    # Hand the template ready-made relative URLs rather than letting it hardcode
    # how many "../" segments separate the rendered HTML from the files it
    # references. Moving any of these directories is then an engine/paths.py change.
    record['bars_url'] = os.path.relpath(
        os.path.join(manifest['bars'], id, date), temp_dir
    )
    record['assets_url'] = os.path.relpath(manifest['assets'], temp_dir)

    # Load the base HTML template
    template_path = 'report.html'
    logging.info(f"Loading base template: {os.path.join(manifest['templates'], template_path)}")

    template = env.get_template(template_path)
    # Render the template with the record data (initially in English).
    # `record=record` additionally exposes the whole dict under one name so the
    # parameter macros can look fields up dynamically, e.g. record['Lead_FF'].
    rendered_html = template.render(record, record=record)
    validate(rendered_html, os.path.join(manifest['templates'], "report.css"))
    # final_html_content will hold the potentially translated HTML
    final_html_content = rendered_html  # Default to original

    if language_code == 'es':
        logging.info("Applying Spanish translation...")
        final_html_content = translate.translate_html(rendered_html, manifest['type'], manifest['type_dir'], config)

    # Remove empty pages and keep table of contents in sync
    final_html_content = layout.remove_empty_pages_and_update_toc(final_html_content)

    # --- Write HTML and Generate PDF ---
    output_file_name = f"{temp_dir}/{date}_{language_code}.html"
    logging.info(f"Writing final HTML report to temp directory: {output_file_name}")
    with open(output_file_name, 'w', encoding='utf-8') as f:
        f.write(final_html_content)
        f.flush()

    # Generate CSS based on the final HTML structure
    layout.generate_custom_css(output_file_name, manifest['templates'], manifest['assets'])

    # --- Construct final PDF filename ---
    final_pdf_filename = _output_filename(record, language, language_code, config)

    # Generate report from the final HTML file, passing the desired final filename and directory
    gen_report(output_file_name, id, final_pdf_filename, language_code, final_report_dir)


def main() -> None:
    # Every path for this run comes from the manifest named by $MANIFEST
    manifest = paths.load_manifest()
    config = paths.load_config(manifest['type'])

    file_path: str = manifest['records']
    os.makedirs(manifest['work'], exist_ok=True)

    # Define and create the final output directory
    final_report_dir = manifest['reports']
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
                # Every field create_report_pdf() needs (id/date/language, display_parameters,
                # water_utility, latest_annual_report_year, ...) is already in the record:
                # analyze() finalizes it at analysis time, not render time.
                create_report_pdf(record, manifest, config)
                processed_records += 1

                if (i + 1) % 10 == 0 or (i + 1) == total_records:
                    elapsed_time = time.time() - start_time
                    logging.info(f"Processed {i + 1}/{total_records} records in {elapsed_time:.2f} seconds.")
            except Exception as e:
                logging.error(f"Failed to process record {i+1} (ID: {record.get('id', record.get('Participant_ID', 'N/A'))}): {e}", exc_info=True)

        end_time = time.time()
        logging.info(f"Finished processing. Successful reports: {processed_records}/{total_records}")
        logging.info(f"Total execution time: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    main()

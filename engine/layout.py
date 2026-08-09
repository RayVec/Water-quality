"""Page-fragment CSS generation, empty-page removal, and TOC page-number
backfill — all keyed off the data-* attribute contract
(docs/multi-type-refactor.md, section 5.2), never off class names or ids:
class names are a design choice that differs per report type, so the engine
cannot rely on `.header .number` or `.heading1` staying the way any one
design happens to spell them.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from bs4 import BeautifulSoup

from engine.pagination import calculate_rendered_heights


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


def generate_custom_css(html_file_path: str, templates_dir: str, assets_dir: str) -> None:
    """Generate a custom CSS file with dynamically calculated page heights.

    Args:
        html_file_path: Path to the rendered HTML file to measure and analyze.
        templates_dir: The type's templates/ directory (source report.css lives here).
        assets_dir: The type's assets/ directory (for the {{ASSETS}} placeholder).
    """
    logging.info(f"Generating custom CSS with dynamic page heights for {html_file_path}")

    # Path to CSS in the temp folder
    temp_folder = os.path.dirname(html_file_path)
    participant_css_path = os.path.join(temp_folder, "report.css")

    if os.path.exists(participant_css_path):
        logging.info(f"Deleting existing CSS file: {participant_css_path}")
        os.remove(participant_css_path)

    # Read the template CSS file
    template_css_path = os.path.join(templates_dir, "report.css")
    with open(template_css_path, 'r', encoding='utf-8') as css_file:
        css_content = css_file.read()

    # The CSS is copied next to the rendered HTML, so its url() references
    # resolve from there. Same reasoning as assets_url in the template: the
    # stylesheet uses an {{ASSETS}} placeholder instead of counting "../".
    css_content = css_content.replace(
        "{{ASSETS}}", os.path.relpath(assets_dir, temp_folder)
    )

    # Determine the pages to measure from the rendered HTML's data-page
    # elements, in document order. validate() already guaranteed at least one
    # exists and that every one has an id (implicitly, via the data-page-content
    # cardinality check finding the element at all) — this doesn't re-check that,
    # it just skips anything unexpectedly id-less rather than crashing.
    with open(html_file_path, 'r', encoding='utf-8') as html_file:
        soup = BeautifulSoup(html_file, 'html.parser')

    pages_to_measure = []
    for element in soup.find_all(attrs={"data-page": True}):
        element_id = element.get('id')
        if element_id:
            pages_to_measure.append(element_id)
        else:
            logging.warning(f"Skipping a data-page element with no id in {html_file_path}")

    if not pages_to_measure:
        logging.error(f"No data-page elements with an id were found in {html_file_path}")

    # Calculate heights for all pages at once, then generate this record's
    # @page height rule and #id { page: ... } assignment for each — the engine
    # writes both from scratch instead of rewriting hand-written ones.
    try:
        # Use the new, optimized function that calculates all heights in a single browser session
        page_heights = calculate_rendered_heights(html_file_path, css_content, pages_to_measure)

        generated_rules = []
        for page_id in pages_to_measure:
            height = page_heights.get(page_id)
            if height is None:
                logging.error(f"Failed to calculate height for {page_id}")
                continue

            # Add 2px padding
            height = height - 30
            logging.info(f"Calculated height for {page_id}: {height}px")

            # Both the print page fragment (@page) and the element itself need
            # the height: the article's own box has to match the page fragment
            # it's assigned to, or its flex layout (space-between header/content/
            # footer) renders against its natural height instead and the footer
            # drifts past the page boundary.
            generated_rules.append(f"@page {page_id} {{\n  height: {height}px;\n}}")
            generated_rules.append(f"#{page_id} {{\n  height: {height}px;\n  page: {page_id};\n}}")

        if generated_rules:
            css_content += "\n\n" + "\n".join(generated_rules) + "\n"
    except Exception as e:
        logging.error(f"Error calculating heights: {str(e)}")

    # Write the updated CSS to the participant's temp directory
    with open(participant_css_path, 'w', encoding='utf-8') as css_file:
        css_file.write(css_content)

    logging.info(f"Custom CSS file created at {participant_css_path}")


def remove_empty_pages_and_update_toc(html_content: str) -> str:
    """Remove empty page articles and update page numbering and table of contents."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove empty pages (skip toc)
    for page in list(soup.find_all(attrs={"data-page": True})):
        if page.get('data-page') == 'toc':
            continue

        content = page.find(attrs={"data-page-content": True})
        if not _content_has_meaningful_data(content):
            logging.info(f"Removing empty page section: {page.get('id', '<no id>')}")
            page.decompose()

    # Rebuild page ordering and id-to-page mapping
    id_to_page: Dict[str, int] = {}
    page_number = 1
    for page in soup.find_all(attrs={"data-page": True}):
        page_id = page.get('id')
        if page_id:
            # Map the page's own id to its page number.
            id_to_page[page_id] = page_number

        # Update every page-number slot on this page (however many there are).
        for number_el in page.find_all(attrs={"data-page-number": True}):
            number_el.string = str(page_number)

        # Map all element ids within this page to the same page number, so
        # anchors pointing at a heading (not the page itself) resolve too.
        for element_with_id in page.find_all(id=True):
            id_to_page[element_with_id['id']] = page_number

        page_number += 1

    # Update table of contents entries based on the new mapping
    toc = soup.find(attrs={"data-page": "toc"})
    if toc:
        for entry in list(toc.find_all(attrs={"data-toc-entry": True})):
            target_id = entry.get('data-toc-entry')
            page_for_target = id_to_page.get(target_id)

            if page_for_target is None:
                logging.info(f"Removing TOC entry without target: {target_id}")
                entry.decompose()
                continue

            page_slot = entry.find(attrs={"data-toc-page": True})
            if page_slot:
                page_slot.string = str(page_for_target)

    return str(soup)

"""Template-attribute contract validation (docs/multi-type-refactor.md, 5.2).

A contract violation means every record in a batch will fail the same way,
so this exits the whole run rather than logging a per-record error and
continuing.
"""
from __future__ import annotations

import re
import sys

from bs4 import BeautifulSoup

# The shared width invariant every type's CSS must declare (see
# docs/multi-type-refactor.md, section 0) — checked here, not chosen per type.
PAGE_WIDTH_PX = 377


def validate(html_content: str, report_css_path: str) -> None:
    """Fail loudly if the rendered template doesn't satisfy the engine's contract."""
    soup = BeautifulSoup(html_content, 'html.parser')

    pages = soup.find_all(attrs={"data-page": True})
    if not pages:
        sys.exit("❌ Template contract violation: no element has a data-page attribute.")

    for page in pages:
        contents = page.find_all(attrs={"data-page-content": True})
        if len(contents) != 1:
            page_id = page.get('id', '<no id>')
            sys.exit(
                f"❌ Template contract violation: page '{page_id}' has {len(contents)} "
                f"data-page-content elements, expected exactly 1."
            )

    ids_in_document = {el['id'] for el in soup.find_all(id=True)}
    for entry in soup.find_all(attrs={"data-toc-entry": True}):
        target = entry.get('data-toc-entry')
        if target not in ids_in_document:
            sys.exit(
                f"❌ Template contract violation: data-toc-entry=\"{target}\" has no matching id in the document."
            )

    css_content = open(report_css_path, encoding='utf-8').read()
    width_match = re.search(r':root\s*\{[^}]*width:\s*(\d+)px', css_content)
    if not width_match or int(width_match.group(1)) != PAGE_WIDTH_PX:
        found = width_match.group(1) if width_match else "none"
        sys.exit(f"❌ Template contract violation: page width is {found}px, expected {PAGE_WIDTH_PX}px.")

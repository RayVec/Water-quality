"""Normalized HTML comparison.

Diagnostic companion to compare_pdf.py: strips insignificant whitespace and
prints a unified diff of the two documents' structure. Structural changes
(new data-* attributes, changed selectors) show up here even when they don't
move a single pixel in the PDF, which is what makes this useful for
confirming a step changed *exactly* what it meant to and nothing else — it
is not itself a pass/fail gate; compare_pdf.py is.
"""
from __future__ import annotations

import difflib
import sys
from typing import List

from bs4 import BeautifulSoup, Comment


def normalize(html_path: str) -> str:
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    for text in soup.find_all(string=True):
        if text.parent and text.parent.name in ("script", "style"):
            continue
        if text.strip() == "":
            text.extract()

    return soup.prettify()


def compare_dom(path_a: str, path_b: str) -> List[str]:
    """Return a unified diff of the normalized documents; empty means identical."""
    text_a = normalize(path_a)
    text_b = normalize(path_b)
    if text_a == text_b:
        return []
    return list(
        difflib.unified_diff(
            text_a.splitlines(),
            text_b.splitlines(),
            fromfile=path_a,
            tofile=path_b,
            lineterm="",
            n=1,
        )
    )


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <baseline.html> <current.html>")
    diffs = compare_dom(sys.argv[1], sys.argv[2])
    if diffs:
        print("\n".join(diffs))
        sys.exit(1)
    print(f"✅ {sys.argv[1]} and {sys.argv[2]} are structurally identical.")


if __name__ == "__main__":
    main()

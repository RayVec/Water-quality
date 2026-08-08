"""Pixel-level PDF comparison.

Compares two PDFs page by page: page count, paper size, and exact pixel
content (rendered at a fixed DPI). This is the authoritative "did the
deliverable change" check for every refactor step — data-* attributes and
other structural changes to the HTML are invisible here if they don't move
a pixel, which is exactly the property each step's "PDF pixel-identical"
acceptance criterion depends on.
"""
from __future__ import annotations

import sys
from typing import List

import pymupdf as fitz
import numpy as np

DPI = 100


def compare_pdfs(path_a: str, path_b: str, dpi: int = DPI) -> List[str]:
    """Return a list of human-readable differences; empty means identical."""
    diffs: List[str] = []
    doc_a = fitz.open(path_a)
    doc_b = fitz.open(path_b)
    try:
        if doc_a.page_count != doc_b.page_count:
            diffs.append(f"page count differs: {doc_a.page_count} vs {doc_b.page_count}")
            return diffs

        for i in range(doc_a.page_count):
            page_a, page_b = doc_a[i], doc_b[i]
            rect_a, rect_b = page_a.rect, page_b.rect
            size_a = (round(rect_a.width, 1), round(rect_a.height, 1))
            size_b = (round(rect_b.width, 1), round(rect_b.height, 1))
            if size_a != size_b:
                diffs.append(f"page {i + 1}: paper size differs: {size_a} vs {size_b}")
                continue

            pix_a = page_a.get_pixmap(dpi=dpi)
            pix_b = page_b.get_pixmap(dpi=dpi)
            if (pix_a.width, pix_a.height) != (pix_b.width, pix_b.height):
                diffs.append(
                    f"page {i + 1}: rendered pixel size differs: "
                    f"{pix_a.width}x{pix_a.height} vs {pix_b.width}x{pix_b.height}"
                )
                continue

            arr_a = np.frombuffer(pix_a.samples, dtype=np.uint8)
            arr_b = np.frombuffer(pix_b.samples, dtype=np.uint8)
            if not np.array_equal(arr_a, arr_b):
                diff_count = int(np.count_nonzero(arr_a != arr_b))
                pct = 100 * diff_count / arr_a.size
                diffs.append(
                    f"page {i + 1}: pixel diff — {diff_count}/{arr_a.size} bytes differ ({pct:.3f}%)"
                )
    finally:
        doc_a.close()
        doc_b.close()
    return diffs


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <baseline.pdf> <current.pdf>")
    diffs = compare_pdfs(sys.argv[1], sys.argv[2])
    if diffs:
        print(f"❌ {sys.argv[1]} vs {sys.argv[2]}:")
        for d in diffs:
            print(f"  - {d}")
        sys.exit(1)
    print(f"✅ {sys.argv[1]} and {sys.argv[2]} are pixel-identical.")


if __name__ == "__main__":
    main()

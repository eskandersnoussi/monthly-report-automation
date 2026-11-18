"""Render the sample report to images for the README and portfolio.

    python demo/make_screenshots.py

Needs PyMuPDF (pip install pymupdf). Builds the October 2026 report from the
fictional sample data, then saves docs/screenshots/page_1.png ... and an
overview image with all pages side by side.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import fitz  # PyMuPDF
import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import report  # noqa: E402

MONTH = "2026-10"
OUT = ROOT / "docs" / "screenshots"
SAMPLES = ROOT / "samples"
CAPTIONS = [
    "Key figures, highlights, daily revenue",
    "Categories and top products",
    "Reorder list, expiry, overstock, costs",
    "12-month trend",
]


def main() -> None:
    report.main(["--month", MONTH])
    pdf_path = ROOT / "reports" / MONTH / f"monthly_report_{MONTH}.pdf"
    xlsx_path = pdf_path.with_suffix(".xlsx")

    SAMPLES.mkdir(exist_ok=True)
    shutil.copy(pdf_path, SAMPLES / pdf_path.name)
    shutil.copy(xlsx_path, SAMPLES / xlsx_path.name)

    OUT.mkdir(parents=True, exist_ok=True)
    pages = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            path = OUT / f"page_{i}.png"
            page.get_pixmap(dpi=130).save(str(path))
            pages.append(path)

    # Overview: all pages side by side on one 1600 x 1000 image.
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor="#0f172a")
    fig.text(0.035, 0.93, "Automated Monthly Report", color="white", fontsize=34,
             fontweight="bold")
    fig.text(0.035, 0.885, "Python builds a PDF + Excel sales, stock and cost report "
             "every month, with no manual work", color="#94a3b8", fontsize=17)
    # Three pages, large enough to read: summary, sales, 12-month trend.
    for i, page in enumerate((0, 1, 3)):
        left = 0.035 + i * 0.315
        ax = fig.add_axes([left, 0.115, 0.30, 0.745])
        ax.imshow(mpimg.imread(pages[page]), aspect="equal")
        ax.set_anchor("N")
        ax.set_axis_off()
        fig.text(left + 0.15, 0.14, CAPTIONS[page], color="#e2e8f0",
                 fontsize=13, ha="center")
    fig.text(0.035, 0.02, f"Fictional demo data. {len(pages)}-page PDF + Excel workbook. "
             "Tools: Python, pandas, matplotlib, fpdf2, openpyxl.",
             color="#94a3b8", fontsize=11.5)
    fig.savefig(OUT / "overview.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved screenshots to {OUT}")


if __name__ == "__main__":
    main()

"""
One-off corpus prep: convert raw .gov HTML pages into clean .txt so the RAG
loader ingests article text without navigation/script boilerplate.

Some sources (USPSTF, NIDDK) are web pages, not PDFs. We strip chrome (nav,
header, footer, scripts, forms) and keep the main article text.

Run once from the repo (rag-eval env):
    python 01-rag-chatbot/src/prepare_sources.py
"""

import re
from pathlib import Path
from bs4 import BeautifulSoup
import shutil
import fitz  # PyMuPDF

DOCS = Path(__file__).resolve().parents[1] / "data" / "documents"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"   # keep original PDFs here

# raw html file -> cleaned txt file + a human title kept at the top for context
SOURCES = {
    "_uspstf.html": (
        "uspstf_diabetes_screening.txt",
        "USPSTF Recommendation: Screening for Prediabetes and Type 2 Diabetes",
    ),
    "_niddk.html": (
        "niddk_managing_diabetes.txt",
        "NIDDK (NIH): Managing Diabetes",
    ),
}

# tags that never carry article content
STRIP_TAGS = ["script", "style", "nav", "header", "footer", "aside", "form",
              "noscript", "button", "svg"]


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for t in soup(STRIP_TAGS):
        t.decompose()

    # prefer the main content container if the page marks one
    main = (soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find("article")
            or soup.body
            or soup)

    text = main.get_text(separator="\n")

    # collapse whitespace: trim lines, drop empties, cap consecutive blanks
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned

def extract_pdf_columns(pdf_path):
    """Extract a two-column PDF in correct reading order.

    pypdf (the default loader) reads straight across the page, interleaving the
    two columns into garbled text. PyMuPDF gives us each text block's position,
    so we read the LEFT column top-to-bottom, then the RIGHT — the way a human
    reads it.
    """
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        mid = page.rect.width / 2
        # each block: (x0, y0, x1, y1, text, block_no, block_type); type 0 = text
        blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        # left column (block center left of the midline) first, each top-to-bottom
        blocks.sort(key=lambda b: (0 if (b[0] + b[2]) / 2 < mid else 1, b[1]))
        pages.append("\n".join(b[4].strip() for b in blocks))
    doc.close()
    text = "\n\n".join(pages)
    text = re.sub(r"\n{3,}", "\n\n", text)   # collapse excess blank lines
    return text


def prepare_fda():
    """Re-extract the FDA (SEGLUROMET) two-column label into clean .txt, and move
    the raw PDF out of the corpus so the loader uses the clean text instead."""
    pdf = DOCS / "fda_metformin_label.pdf"
    if not pdf.exists():
        print("SKIP  fda_metformin_label.pdf (not found — already prepared?)")
        return
    text = extract_pdf_columns(pdf)
    out = DOCS / "fda_metformin_label.txt"
    out.write_text(text, encoding="utf-8")
    print(f"OK    fda_metformin_label.pdf -> {out.name}  ({len(text):,} chars)")
    RAW.mkdir(exist_ok=True)
    shutil.move(str(pdf), str(RAW / pdf.name))   # keep original, out of the corpus
    print(f"      moved raw PDF to data/{RAW.name}/")

def main() -> None:
    for raw_name, (out_name, title) in SOURCES.items():
        raw_path = DOCS / raw_name
        if not raw_path.exists():
            print(f"SKIP  {raw_name} (not found)")
            continue

        cleaned = clean_html(raw_path.read_text(encoding="utf-8", errors="ignore"))
        out_path = DOCS / out_name
        out_path.write_text(f"{title}\n\n{cleaned}\n", encoding="utf-8")
        print(f"OK    {raw_name} -> {out_name}  ({len(cleaned):,} chars)")

        raw_path.unlink()  # remove raw html once cleaned
        print(f"      removed raw {raw_name}")
    prepare_fda()

if __name__ == "__main__":
    main()

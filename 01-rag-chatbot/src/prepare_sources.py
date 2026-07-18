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

DOCS = Path(__file__).resolve().parents[1] / "data" / "documents"

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


if __name__ == "__main__":
    main()

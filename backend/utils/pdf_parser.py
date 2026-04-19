import pdfplumber


def extract_pages(file_path: str) -> list[dict]:
    """Lightweight text+table extraction; used outside the agent graph."""
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            pages.append({
                "page_num": i,
                "text": page.extract_text() or "",
                "tables": page.extract_tables() or [],
            })
    return pages

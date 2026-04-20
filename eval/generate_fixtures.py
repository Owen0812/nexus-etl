"""Generate synthetic test fixtures: 10 plain-text PDFs + 10 table-heavy PDFs.

Usage:
    python -m eval.generate_fixtures --out eval/fixtures
"""
from __future__ import annotations

import argparse
import json
import random
import string
from pathlib import Path


def _random_sentence(min_words: int = 8, max_words: int = 20) -> str:
    words = [
        "algorithm", "pipeline", "document", "extraction", "semantic",
        "vector", "knowledge", "enterprise", "baseline", "quality",
        "threshold", "metadata", "embedding", "retrieval", "analysis",
    ]
    n = random.randint(min_words, max_words)
    sentence = " ".join(random.choices(words, k=n))
    return sentence.capitalize() + "."


def _make_plain_pdf(path: Path, doc_id: int) -> dict:
    """Create a plain-text PDF with ~3 paragraphs and return ground-truth metadata."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    title = f"Plain Document {doc_id:02d}"
    author = f"Author {chr(65 + doc_id % 26)}"
    paragraphs = [" ".join(_random_sentence() for _ in range(6)) for _ in range(3)]

    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(title)
    c.setAuthor(author)

    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 11)
    for para in paragraphs:
        # Wrap at ~90 chars
        words = para.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > 90:
                c.drawString(50, y, line)
                y -= 18
                line = word
            else:
                line = (line + " " + word).strip()
        if line:
            c.drawString(50, y, line)
            y -= 18
        y -= 10
    c.save()

    key_sentences = [s.strip() for para in paragraphs for s in para.split(".") if len(s.strip()) > 20]
    return {
        "file": path.name,
        "type": "plain",
        "ground_truth": {
            "metadata": {"title": title, "author": author},
            "tables": [],
            "key_sentences": key_sentences[:5],
        },
    }


def _make_table_pdf(path: Path, doc_id: int) -> dict:
    """Create a table-heavy PDF with 2 tables and return ground-truth table data."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    title = f"Table Document {doc_id:02d}"
    author = f"Author {chr(65 + (doc_id + 10) % 26)}"

    headers = ["ID", "Name", "Score", "Category", "Notes"]
    rows_1 = [headers] + [
        [str(i), f"Item {i}", str(round(random.uniform(0.5, 1.0), 2)),
         random.choice(["A", "B", "C"]), _random_sentence(3, 6)]
        for i in range(1, 12)
    ]
    rows_2 = [["Quarter", "Revenue", "Growth"]] + [
        [f"Q{q} 2024", f"${random.randint(100, 999)}K", f"{random.randint(-10, 30)}%"]
        for q in range(1, 5)
    ]

    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 12),
        Paragraph("Performance Metrics", styles["Heading2"]),
        Table(rows_1, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ])),
        Spacer(1, 24),
        Paragraph("Financial Summary", styles["Heading2"]),
        Table(rows_2, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ])),
    ]
    doc.build(story)

    return {
        "file": path.name,
        "type": "table",
        "ground_truth": {
            "metadata": {"title": title, "author": author},
            "tables": [rows_1, rows_2],
            "key_sentences": [],
        },
    }


def generate(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import reportlab  # noqa: F401
    except ImportError:
        print("reportlab not installed — skipping PDF generation. pip install reportlab")
        return

    manifest: list[dict] = []

    for i in range(1, 11):
        path = out_dir / f"plain_{i:02d}.pdf"
        manifest.append(_make_plain_pdf(path, i))
        print(f"  created {path.name}")

    for i in range(1, 11):
        path = out_dir / f"table_{i:02d}.pdf"
        manifest.append(_make_table_pdf(path, i))
        print(f"  created {path.name}")

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nManifest written to {out_dir}/manifest.json ({len(manifest)} fixtures)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="eval/fixtures", help="Output directory")
    args = parser.parse_args()
    generate(Path(args.out))

"""Generate a Markdown comparison report from eval/results.json.

Usage:
    python -m eval.report --results eval/results.json --out eval/report.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def generate(results_path: Path, out_path: Path) -> str:
    raw = json.loads(results_path.read_text(encoding="utf-8"))
    # Support both old list format and new {results, search_latency} format
    data: list[dict] = raw if isinstance(raw, list) else raw.get("results", [])
    search_latency: dict = {} if isinstance(raw, list) else raw.get("search_latency", {})
    valid = [r for r in data if "nexus" in r]

    lines = [
        "# Nexus ETL — Evaluation Report",
        "",
        f"**Total fixtures:** {len(data)}  |  **Valid runs:** {len(valid)}",
        "",
        "## Per-file Results",
        "",
        "| File | Type | SC (nexus) | TBL (nexus) | Chunks (nexus) | Chunks (fixed) | Chunks (unstr) |",
        "|------|------|:----------:|:-----------:|:--------------:|:--------------:|:--------------:|",
    ]

    for r in valid:
        nexus = r["nexus"]
        fixed = r.get("baseline_fixed", {})
        unst = r.get("baseline_unstructured", {})
        lines.append(
            f"| {r['file']} | {r['type']} "
            f"| {nexus['semantic_completeness']:.2f} "
            f"| {nexus['table_accuracy']:.2f} "
            f"| {nexus['chunk_count']} "
            f"| {fixed.get('chunk_count', '-')} "
            f"| {unst.get('chunk_count', '-')} |"
        )

    if valid:
        avg_sc   = sum(r["nexus"]["semantic_completeness"] for r in valid) / len(valid)
        avg_tbl  = sum(r["nexus"]["table_accuracy"] for r in valid) / len(valid)
        avg_n    = sum(r["nexus"]["chunk_count"] for r in valid) / len(valid)
        avg_f    = sum(r.get("baseline_fixed", {}).get("chunk_count", 0) for r in valid) / len(valid)
        avg_u    = sum(r.get("baseline_unstructured", {}).get("chunk_count", 0) for r in valid) / len(valid)
        avg_tput = sum(r["nexus"].get("throughput_pages_per_min", 0) for r in valid) / len(valid)

        lines += [
            f"| **Average** | — | **{avg_sc:.2f}** | **{avg_tbl:.2f}** "
            f"| **{avg_n:.1f}** | {avg_f:.1f} | {avg_u:.1f} |",
            "",
            "## Engineering Metrics",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Avg throughput | {avg_tput:.1f} pages/min |",
        ]
        if search_latency:
            lines += [
                f"| Search P50 | {search_latency.get('p50_ms', '-')} ms |",
                f"| Search P95 | {search_latency.get('p95_ms', '-')} ms |",
                f"| Search P99 | {search_latency.get('p99_ms', '-')} ms |",
            ]

        lines += [
            "",
            "## Metric Definitions",
            "",
            "- **SC**: Semantic Completeness — fraction of key sentences from GT found in any chunk",
            "- **TBL**: Table Reconstruction Accuracy — cell-level recall vs ground-truth tables",
            "- **Chunks**: number of output chunks (lower = more consolidated; higher = finer-grained)",
            "- **Throughput**: pages processed per minute (higher = faster pipeline)",
            "- **Search P50/P99**: end-to-end retrieval latency at 50th/99th percentile",
        ]

    errors = [r for r in data if "error" in r]
    if errors:
        lines += ["", "## Errors", ""]
        for r in errors:
            lines.append(f"- `{r['file']}`: {r['error']}")

    report = "\n".join(lines) + "\n"
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to {out_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="eval/results.json")
    parser.add_argument("--out", default="eval/report.md")
    args = parser.parse_args()
    generate(Path(args.results), Path(args.out))

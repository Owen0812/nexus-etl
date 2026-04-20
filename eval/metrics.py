"""Evaluation metrics for Nexus ETL vs baselines."""
from __future__ import annotations

import re
from typing import Any


def semantic_completeness(original_sentences: list[str], chunks: list[str]) -> float:
    """Fraction of key sentences from the original that appear (substring) in any chunk."""
    if not original_sentences:
        return 1.0
    all_text = "\n".join(chunks).lower()
    hits = sum(1 for s in original_sentences if s.lower().strip() in all_text)
    return hits / len(original_sentences)


def table_reconstruction_accuracy(
    ground_truth_tables: list[list[list[str]]],
    extracted_tables: list[list[list[str]]],
) -> float:
    """Cell-level accuracy: fraction of GT cells found in extracted tables (order-insensitive)."""
    gt_cells: set[str] = set()
    for tbl in ground_truth_tables:
        for row in tbl:
            for cell in row:
                if cell.strip():
                    gt_cells.add(cell.strip().lower())
    if not gt_cells:
        return 1.0

    ex_cells: set[str] = set()
    for tbl in extracted_tables:
        for row in tbl:
            for cell in row:
                if cell.strip():
                    ex_cells.add(cell.strip().lower())

    return len(gt_cells & ex_cells) / len(gt_cells)


def metadata_f1(
    ground_truth: dict[str, Any],
    predicted: dict[str, Any],
) -> dict[str, float]:
    """Token-level F1 for each metadata field (title, author, etc.)."""

    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"\w+", text.lower()))

    results: dict[str, float] = {}
    all_keys = set(ground_truth) | set(predicted)
    for key in all_keys:
        gt_tokens = _tokens(str(ground_truth.get(key, "")))
        pred_tokens = _tokens(str(predicted.get(key, "")))
        if not gt_tokens and not pred_tokens:
            results[key] = 1.0
            continue
        if not gt_tokens or not pred_tokens:
            results[key] = 0.0
            continue
        precision = len(gt_tokens & pred_tokens) / len(pred_tokens)
        recall = len(gt_tokens & pred_tokens) / len(gt_tokens)
        if precision + recall == 0:
            results[key] = 0.0
        else:
            results[key] = 2 * precision * recall / (precision + recall)
    return results


def token_savings_ratio(full_token_count: int, processed_token_count: int) -> float:
    """Ratio of tokens saved by incremental dedup (0–1). 1 = fully skipped."""
    if full_token_count == 0:
        return 0.0
    return max(0.0, 1.0 - processed_token_count / full_token_count)


def latency_percentiles(latencies_s: list[float]) -> dict[str, float]:
    """Compute P50 / P95 / P99 from a list of latency samples (seconds).

    Returns values in milliseconds for readability.
    """
    if not latencies_s:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
    sorted_ms = sorted(x * 1000 for x in latencies_s)
    n = len(sorted_ms)

    def _pct(p: float) -> float:
        idx = (p / 100) * (n - 1)
        lo, frac = int(idx), idx - int(idx)
        if lo + 1 < n:
            return round(sorted_ms[lo] + frac * (sorted_ms[lo + 1] - sorted_ms[lo]), 1)
        return round(sorted_ms[lo], 1)

    return {"p50_ms": _pct(50), "p95_ms": _pct(95), "p99_ms": _pct(99)}


def throughput_pages_per_minute(total_pages: int, elapsed_s: float) -> float:
    """Pages processed per minute."""
    if elapsed_s <= 0:
        return 0.0
    return round(total_pages / elapsed_s * 60, 1)

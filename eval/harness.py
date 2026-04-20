"""Nexus ETL Evaluation Harness.

Modes:
  --mode api     Call the running FastAPI service (requires server + Celery running)
  --mode direct  Import and run the LangGraph pipeline in-process (no server needed)

Usage:
    # Generate fixtures first:
    python -m eval.generate_fixtures --out eval/fixtures

    # Run harness (direct mode, no server needed):
    python -m eval.harness --mode direct --fixtures eval/fixtures --out eval/results.json

    # Run harness against live API (also benchmarks search latency):
    python -m eval.harness --mode api --base-url http://localhost:8000 --fixtures eval/fixtures
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from eval.metrics import (
    latency_percentiles,
    metadata_f1,
    semantic_completeness,
    table_reconstruction_accuracy,
    throughput_pages_per_minute,
    token_savings_ratio,
)
from eval.baselines.chunker_fixed import process_file as baseline_fixed
from eval.baselines.unstructured_raw import process_file as baseline_unstructured


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_manifest(fixtures_dir: Path) -> list[dict]:
    manifest_path = fixtures_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"No manifest.json in {fixtures_dir}. Run: python -m eval.generate_fixtures"
        )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _chunks_to_texts(chunks: list[dict]) -> list[str]:
    return [c.get("content", "") for c in chunks]


def _count_pages(file_path: str) -> int:
    """Best-effort page/section count for throughput metric."""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            return len(pdf.pages)
    except Exception:
        return 1


# ── Pipeline runners ──────────────────────────────────────────────────────────

async def _run_direct(file_path: str) -> list[dict]:
    """Run graph in-process (no server). Returns list of chunk dicts."""
    import hashlib
    import sys
    sys.path.insert(0, str(Path(__file__).parents[1]))

    from backend.agents.graph import pipeline_graph

    file_hash = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
    state = {
        "document_id": "eval-test",
        "file_path": file_path,
        "filename": Path(file_path).name,
        "file_hash": file_hash,
        "is_duplicate": False,
        "raw_pages": [],
        "extracted_tables": [],
        "extracted_images": [],
        "raw_chunks": [],
        "doc_metadata": {},
        "chunk_metadata": [],
        "filtered_chunks": [],
        "quality_report": {},
        "processing_strategy": "",
        "current_stage": "",
        "stages_completed": [],
        "error": None,
        "retry_count": 0,
        "messages": [],
    }

    config = {"configurable": {"thread_id": "eval-thread"}}
    final = None
    async for snapshot in pipeline_graph.astream(state, config=config, stream_mode="values"):
        final = snapshot

    if final is None:
        return []
    return final.get("filtered_chunks", [])


def _run_api(file_path: str, base_url: str) -> list[dict]:
    """Upload file to live API, poll until done, fetch chunks."""
    import httpx

    with httpx.Client(base_url=base_url, timeout=120) as client:
        with open(file_path, "rb") as f:
            resp = client.post("/api/v1/documents/upload", files={"file": f})
        resp.raise_for_status()
        data = resp.json()
        doc_id = data["document_id"]
        task_id = data["task_id"]

        for _ in range(120):
            r = client.get(f"/api/v1/pipelines/task/{task_id}")
            r.raise_for_status()
            if r.json().get("status") in ("SUCCESS", "FAILURE"):
                break
            time.sleep(2)

        chunks_resp = client.get(f"/api/v1/documents/{doc_id}/chunks?limit=500")
        chunks_resp.raise_for_status()
        return chunks_resp.json()


def _bench_search_latency(base_url: str, sample_queries: list[str], n_runs: int = 5) -> dict:
    """Hit the search API with sample queries; return P50/P95/P99 latencies."""
    import httpx

    latencies: list[float] = []
    with httpx.Client(base_url=base_url, timeout=30) as client:
        for _ in range(n_runs):
            for query in sample_queries:
                t0 = time.perf_counter()
                try:
                    r = client.post("/api/v1/search/", json={"query": query, "top_k": 5})
                    r.raise_for_status()
                    # prefer server-measured latency if available
                    server_ms = r.json().get("latency_ms")
                    if server_ms:
                        latencies.append(server_ms / 1000)
                    else:
                        latencies.append(time.perf_counter() - t0)
                except Exception:
                    latencies.append(time.perf_counter() - t0)
    return latency_percentiles(latencies)


# ── Evaluation loop ───────────────────────────────────────────────────────────

async def evaluate_one(
    fixture: dict,
    fixtures_dir: Path,
    mode: str,
    base_url: str,
) -> dict:
    file_path = str(fixtures_dir / fixture["file"])
    gt = fixture.get("ground_truth", {})

    # Run Nexus ETL
    t0 = time.perf_counter()
    if mode == "direct":
        nexus_chunks = await _run_direct(file_path)
    else:
        nexus_chunks = _run_api(file_path, base_url)
    nexus_elapsed = time.perf_counter() - t0

    nexus_texts = _chunks_to_texts(nexus_chunks)
    nexus_tables = [c.get("data", []) for c in nexus_chunks if c.get("chunk_type") == "table"]

    # Baselines
    t1 = time.perf_counter()
    fixed_chunks = baseline_fixed(file_path)
    fixed_elapsed = time.perf_counter() - t1

    t2 = time.perf_counter()
    try:
        unst_chunks = baseline_unstructured(file_path)
    except Exception as e:
        unst_chunks = [{"content": f"ERROR: {e}", "chunk_type": "error"}]
    unst_elapsed = time.perf_counter() - t2

    # Metrics
    key_sentences = gt.get("key_sentences", [])
    gt_tables = gt.get("tables", [])
    gt_meta = gt.get("metadata", {})
    pages = _count_pages(file_path)

    nexus_meta = {}
    if nexus_chunks and isinstance(nexus_chunks[0].get("chunk_metadata"), dict):
        nexus_meta = nexus_chunks[0]["chunk_metadata"].get("doc_metadata", {})

    return {
        "file": fixture["file"],
        "type": fixture["type"],
        "pages": pages,
        "nexus": {
            "chunk_count": len(nexus_chunks),
            "semantic_completeness": semantic_completeness(key_sentences, nexus_texts),
            "table_accuracy": table_reconstruction_accuracy(gt_tables, nexus_tables),
            "metadata_f1": metadata_f1(gt_meta, nexus_meta),
            "elapsed_s": round(nexus_elapsed, 2),
            "throughput_pages_per_min": throughput_pages_per_minute(pages, nexus_elapsed),
        },
        "baseline_fixed": {
            "chunk_count": len(fixed_chunks),
            "semantic_completeness": semantic_completeness(key_sentences, _chunks_to_texts(fixed_chunks)),
            "elapsed_s": round(fixed_elapsed, 2),
            "throughput_pages_per_min": throughput_pages_per_minute(pages, fixed_elapsed),
        },
        "baseline_unstructured": {
            "chunk_count": len(unst_chunks),
            "semantic_completeness": semantic_completeness(key_sentences, _chunks_to_texts(unst_chunks)),
            "elapsed_s": round(unst_elapsed, 2),
            "throughput_pages_per_min": throughput_pages_per_minute(pages, unst_elapsed),
        },
    }


async def run_eval(
    fixtures_dir: Path,
    mode: str,
    base_url: str,
    out_path: Path,
    limit: int | None,
) -> None:
    manifest = _load_manifest(fixtures_dir)
    if limit:
        manifest = manifest[:limit]

    results = []
    pipeline_latencies: list[float] = []

    for i, fixture in enumerate(manifest, 1):
        print(f"[{i}/{len(manifest)}] {fixture['file']} ...", end=" ", flush=True)
        try:
            r = await evaluate_one(fixture, fixtures_dir, mode, base_url)
            pipeline_latencies.append(r["nexus"]["elapsed_s"])
            print(
                f"chunks={r['nexus']['chunk_count']}  "
                f"sc={r['nexus']['semantic_completeness']:.2f}  "
                f"tbl={r['nexus']['table_accuracy']:.2f}  "
                f"{r['nexus']['throughput_pages_per_min']:.1f} pg/min"
            )
        except Exception as e:
            print(f"ERROR: {e}")
            r = {"file": fixture["file"], "error": str(e)}
        results.append(r)

    # Search latency benchmark (API mode only)
    search_latency_stats: dict = {}
    if mode == "api":
        print("\nBenchmarking search latency (10 queries × 5 runs)...")
        sample_queries = [
            "revenue growth", "key findings", "table summary",
            "main conclusion", "data analysis", "performance metrics",
            "quarterly results", "methodology", "abstract", "recommendations",
        ]
        search_latency_stats = _bench_search_latency(base_url, sample_queries[:5])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = {"results": results, "search_latency": search_latency_stats}
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to {out_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    valid = [r for r in results if "nexus" in r]
    if valid:
        avg_sc   = sum(r["nexus"]["semantic_completeness"] for r in valid) / len(valid)
        avg_tbl  = sum(r["nexus"]["table_accuracy"] for r in valid) / len(valid)
        avg_tput = sum(r["nexus"]["throughput_pages_per_min"] for r in valid) / len(valid)
        avg_nc   = sum(r["nexus"]["chunk_count"] for r in valid) / len(valid)
        avg_fc   = sum(r["baseline_fixed"]["chunk_count"] for r in valid) / len(valid)
        pct      = latency_percentiles(pipeline_latencies)

        print(f"\n── Quality Metrics ({len(valid)} fixtures) ──────────────────────────")
        print(f"  Semantic completeness (avg) : {avg_sc:.3f}")
        print(f"  Table reconstruction (avg)  : {avg_tbl:.3f}")
        print(f"  Chunk count  nexus / fixed  : {avg_nc:.1f} / {avg_fc:.1f}")
        print(f"\n── Engineering Metrics ──────────────────────────────────────────────")
        print(f"  Pipeline throughput (avg)   : {avg_tput:.1f} pages/min")
        print(f"  Pipeline latency  P50       : {pct['p50_ms']:.0f} ms")
        print(f"  Pipeline latency  P95       : {pct['p95_ms']:.0f} ms")
        print(f"  Pipeline latency  P99       : {pct['p99_ms']:.0f} ms")
        if search_latency_stats:
            print(f"\n── Search Latency ───────────────────────────────────────────────────")
            print(f"  Search P50                  : {search_latency_stats['p50_ms']:.0f} ms")
            print(f"  Search P95                  : {search_latency_stats['p95_ms']:.0f} ms")
            print(f"  Search P99                  : {search_latency_stats['p99_ms']:.0f} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nexus ETL Evaluation Harness")
    parser.add_argument("--mode", choices=["api", "direct"], default="direct")
    parser.add_argument("--fixtures", default="eval/fixtures")
    parser.add_argument("--out", default="eval/results.json")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--limit", type=int, default=None, help="Max fixtures to evaluate")
    args = parser.parse_args()

    asyncio.run(run_eval(
        fixtures_dir=Path(args.fixtures),
        mode=args.mode,
        base_url=args.base_url,
        out_path=Path(args.out),
        limit=args.limit,
    ))

"""Evaluate a running LabKB instance; no document content is sent anywhere else."""

import argparse
import json
import math
import os
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv


def percentile(values, percentile_value):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percentile_value) - 1)] if ordered else None


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="检索与问答评测（不测首 token 延迟）")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--questions", type=Path, default=Path("examples/eval.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/benchmark.json"))
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("repeat 必须 >= 1")
    questions = [
        json.loads(line)
        for line in args.questions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not questions:
        parser.error("问题集为空")
    token = os.getenv("LABKB_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    rows = []
    with httpx.Client(
        base_url=args.base_url, headers=headers, timeout=300, trust_env=False
    ) as client:
        response = client.get("/api/status")
        response.raise_for_status()
        status = response.json()
        for run in range(args.repeat):
            for case in questions:
                row = {"id": case["id"], "run": run + 1, "question": case["question"]}
                try:
                    search = client.post(
                        "/api/search", json={"query": case["question"], "top_k": 4}
                    )
                    search.raise_for_status()
                    found = {h["document_name"] for h in search.json()["hits"]}
                    expected = set(case.get("expected_documents", []))
                    row["recall_at_4"] = len(found & expected) / len(expected) if expected else None
                    started = time.perf_counter()
                    chat = client.post(
                        "/api/chat",
                        json={"message": case["question"], "history": case.get("history", [])},
                    )
                    row["end_to_end_ms"] = round((time.perf_counter() - started) * 1000, 2)
                    chat.raise_for_status()
                    answer = chat.json()
                    row.update(
                        answer=answer["answer"],
                        refused=answer["refused"],
                        refusal_correct=answer["refused"] == case["expect_refusal"],
                        citations=answer["citations"],
                        usage=answer["usage"],
                        citation_validated=answer["citation_validated"],
                    )
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    row["error"] = type(exc).__name__
                rows.append(row)
                print(f"{row['id']}: {'ERROR' if 'error' in row else 'done'}")
    successful = [r for r in rows if "error" not in r]
    recalls = [r["recall_at_4"] for r in successful if r["recall_at_4"] is not None]
    latencies = [r["end_to_end_ms"] for r in successful]
    speeds = [
        r["usage"].get("tokens_per_second")
        for r in successful
        if r["usage"].get("tokens_per_second")
    ]
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "status": status,
        "cases": len(rows),
        "errors": len(rows) - len(successful),
        "recall_at_4": statistics.mean(recalls) if recalls else None,
        "refusal_accuracy": statistics.mean(r["refusal_correct"] for r in successful)
        if successful
        else None,
        "mean_end_to_end_ms": statistics.mean(latencies) if latencies else None,
        "p50_end_to_end_ms": percentile(latencies, 0.5),
        "p95_end_to_end_ms": percentile(latencies, 0.95),
        "mean_generation_tokens_per_second": statistics.mean(speeds) if speeds else None,
        "notes": "演示模式没有模型速度；非流式接口不测 TTFT。引用归属检查不是事实核验。失败样本不计入平均指标，须同时查看 errors。",
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "results"}, ensure_ascii=False, indent=2
        )
    )
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Memory-model bake-off runner.

Drives the REAL extractor (agents.memory_extractor.MemoryExtractor) and the REAL
judge pipeline (database.memory_quality_judge.evaluate_memory) across a set of
candidate OpenRouter models, on the curated fixtures.

- JUDGE eval is objective: each labeled fact is classified accept/reject by the
  real pipeline; we compare to the ground-truth label and report accuracy /
  precision / recall per candidate. (No grader needed — we know the answers.)
- EXTRACTOR eval emits each candidate's extracted memories per fixture to a JSON
  report + readable console dump, to be graded by reading them (Claude grades
  in-conversation; no extra grader API call).

Usage:
    python evals/memory/run_eval.py                  # all candidates, both evals
    python evals/memory/run_eval.py --only-judge
    python evals/memory/run_eval.py --only-extractor
    python evals/memory/run_eval.py --models deepseek/deepseek-v4-flash,x-ai/grok-4.3

Costs real OpenRouter tokens. Not a pytest test.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from evals.memory.fixtures import EXTRACTOR_FIXTURES, JUDGE_FIXTURES  # noqa: E402

CANDIDATES = [
    "deepseek/deepseek-v4-flash",
    "qwen/qwen3.6-flash",
    "tencent/hy3-preview",
    "mistralai/mistral-small-2603",
    "x-ai/grok-4.3",  # incumbent extractor baseline
]

REPORT_DIR = Path(__file__).resolve().parent / "results"


# --------------------------------------------------------------------------
# Extractor eval
# --------------------------------------------------------------------------

async def run_extractor_for_model(model: str) -> dict:
    from agents.memory_extractor import MemoryExtractor

    extractor = MemoryExtractor()
    extractor.model_name = model  # override the env/default model

    out = {"model": model, "fixtures": [], "error": None, "elapsed_s": 0.0}
    t0 = time.time()
    for fx in EXTRACTOR_FIXTURES:
        rec = {"id": fx["id"], "extracted": [], "summary": None, "error": None}
        try:
            result = await extractor.extract_memories(
                conversation_history=fx["conversation"],
                conversation_id=f"eval_{fx['id']}",
                existing_memories=[],
            )
            rec["summary"] = result.summary
            rec["extracted"] = [
                {
                    "fact": m.fact,
                    "category": m.category,
                    "confidence": round(m.confidence, 2),
                    "is_ephemeral": m.is_ephemeral,
                }
                for m in result.memories
            ]
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        out["fixtures"].append(rec)
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


# --------------------------------------------------------------------------
# Judge eval (objective: classify labeled facts, compare to ground truth)
# --------------------------------------------------------------------------

async def run_judge_for_model(model: str) -> dict:
    import database.memory_quality_judge as judge

    judge.JUDGE_MODEL = model  # module global is read at call time

    out = {"model": model, "facts": [], "error": None, "elapsed_s": 0.0,
           "tp": 0, "fp": 0, "tn": 0, "fn": 0}
    t0 = time.time()
    for jf in JUDGE_FIXTURES:
        rec = {"fact": jf["fact"], "label": jf["label"], "action": None,
               "weighted": None, "predicted": None, "correct": None, "error": None}
        try:
            decision, score = await judge.evaluate_memory(
                candidate_fact=jf["fact"],
                candidate_category=jf["category"],
                candidate_embedding=[0.0],          # no existing mems -> unused
                existing_memories=[],
                user_context="",
                user_id="eval-operator",
            )
            predicted = "reject" if decision.action == "REJECT" else "accept"
            rec["action"] = decision.action
            rec["weighted"] = round(score.weighted_score, 2)
            rec["predicted"] = predicted
            rec["correct"] = (predicted == jf["label"])
            # confusion (positive class = "accept")
            if jf["label"] == "accept" and predicted == "accept":
                out["tp"] += 1
            elif jf["label"] == "reject" and predicted == "accept":
                out["fp"] += 1
            elif jf["label"] == "reject" and predicted == "reject":
                out["tn"] += 1
            else:
                out["fn"] += 1
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        out["facts"].append(rec)
    out["elapsed_s"] = round(time.time() - t0, 1)
    total = out["tp"] + out["fp"] + out["tn"] + out["fn"]
    out["accuracy"] = round((out["tp"] + out["tn"]) / total, 3) if total else None
    prec_den = out["tp"] + out["fp"]
    rec_den = out["tp"] + out["fn"]
    out["precision"] = round(out["tp"] / prec_den, 3) if prec_den else None
    out["recall"] = round(out["tp"] / rec_den, 3) if rec_den else None
    return out


# --------------------------------------------------------------------------

def _print_judge_summary(judge_results: list[dict]):
    print("\n" + "=" * 78)
    print("JUDGE EVAL — classify labeled facts (accept=keep, reject=drop)")
    print(f"  {len(JUDGE_FIXTURES)} facts | accept=positive class | accuracy higher=better")
    print("=" * 78)
    print(f"{'model':<32} {'acc':>6} {'prec':>6} {'rec':>6} {'fp':>4} {'fn':>4} {'err':>4} {'sec':>6}")
    print("-" * 78)
    for r in judge_results:
        errs = sum(1 for f in r["facts"] if f["error"])
        print(f"{r['model']:<32} {str(r.get('accuracy','-')):>6} {str(r.get('precision','-')):>6} "
              f"{str(r.get('recall','-')):>6} {r['fp']:>4} {r['fn']:>4} {errs:>4} {r['elapsed_s']:>6}")
    print("-" * 78)
    print("fp = false-positive (kept junk, BAD) | fn = false-negative (dropped a good memory)")


def _print_extractor_dump(ext_results: list[dict]):
    print("\n" + "=" * 78)
    print("EXTRACTOR EVAL — per-fixture extracted memories (grade by reading)")
    print("=" * 78)
    for fx in EXTRACTOR_FIXTURES:
        print(f"\n### FIXTURE: {fx['id']}")
        print(f"  expected_save  : {[e['gist'] for e in fx['expected_save']]}")
        print(f"  expected_reject: {fx['expected_reject']}")
        for r in ext_results:
            frec = next((f for f in r["fixtures"] if f["id"] == fx["id"]), None)
            if not frec:
                continue
            if frec["error"]:
                print(f"  [{r['model']}] ERROR: {frec['error']}")
                continue
            mems = frec["extracted"]
            print(f"  [{r['model']}] {len(mems)} memories:")
            for m in mems:
                eph = " (ephemeral)" if m["is_ephemeral"] else ""
                print(f"      - ({m['category']}, {m['confidence']}){eph} {m['fact']}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated model slugs (default: all candidates)")
    ap.add_argument("--only-judge", action="store_true")
    ap.add_argument("--only-extractor", action="store_true")
    args = ap.parse_args()

    models = args.models.split(",") if args.models else CANDIDATES
    do_judge = not args.only_extractor
    do_ext = not args.only_judge

    report = {"ts": datetime.utcnow().isoformat(), "models": models}

    ext_results = []
    if do_ext:
        print(f"Running extractor eval: {len(models)} models x {len(EXTRACTOR_FIXTURES)} fixtures...")
        ext_results = await asyncio.gather(*(run_extractor_for_model(m) for m in models))
        report["extractor"] = ext_results
        _print_extractor_dump(ext_results)

    judge_results = []
    if do_judge:
        print(f"\nRunning judge eval: {len(models)} models x {len(JUDGE_FIXTURES)} facts...")
        judge_results = await asyncio.gather(*(run_judge_for_model(m) for m in models))
        report["judge"] = judge_results
        _print_judge_summary(judge_results)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"eval_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nFull JSON report: {path}")


if __name__ == "__main__":
    asyncio.run(main())

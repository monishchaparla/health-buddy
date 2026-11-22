"""Score the meal parser against the labelled set in meals.json.

python -m evals.run                   # rules baseline (no API calls)
python -m evals.run --engine gemini   # Gemini; outputs cached in evals/runs/ so reruns cost nothing

What is measured (and what isn't): whether the parser names the right foods and portions. Expected
calories use the same food database as the app, so the calorie error (MAPE) is parser error only,
not database error versus a lab measurement.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from healthbuddy import foods, gemini, nutrition, parse

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PACE_S = 4  # the free tier is shared with another project; stay well under its rate limit


def expected_kcal(items: list[dict]) -> float:
    total = 0.0
    for it in items:
        f = foods.get(it["food"])
        total += nutrition.nutrients(f["per100"], nutrition.grams_for(f, it["qty"], it["unit"]))["kcal"]
    return total


def predict(engine: str, meals: list[dict]) -> dict[str, list[dict]]:
    if engine == "rules":
        return {m["id"]: parse.parse_rules(m["text"]) for m in meals}
    cache_path = RUNS / f"{engine}.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    for m in meals:
        if m["id"] in cache:
            continue
        try:
            items, model = parse.parse_text_ai(m["text"])
            cache[m["id"]] = {"model": model, "items": items}
        except gemini.AIUnavailable as exc:  # includes RateLimited: stop, keep what we have, rerun later
            print(f"stopped at {m['id']}: {exc}")
            break
        RUNS.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(PACE_S)
    return {k: v["items"] for k, v in cache.items()}


def score(meals: list[dict], preds: dict[str, list[dict]]) -> dict:
    tp = n_pred = n_gold = portion_ok = 0
    errors: list[float] = []
    by_lang: dict[str, list[float]] = {}
    misses = []
    scored = [m for m in meals if m["id"] in preds]
    for m in scored:
        pred = [p for p in preds[m["id"]]]
        pred_ids = Counter(p["food"]["id"] for p in pred if p["matched"])
        gold_ids = Counter(i["food"] for i in m["items"])
        hit = sum((pred_ids & gold_ids).values())
        tp += hit
        n_pred += len(pred)  # unmatched predictions count as wrong
        n_gold += sum(gold_ids.values())
        for g in m["items"]:
            p = next((p for p in pred if p["matched"] and p["food"]["id"] == g["food"]), None)
            if p:
                want = nutrition.grams_for(foods.get(g["food"]), g["qty"], g["unit"])
                portion_ok += abs(p["grams"] - want) <= 0.1 * want
        got = sum(p["nutrients"]["kcal"] for p in pred if p["matched"])
        exp = expected_kcal(m["items"])
        err = abs(got - exp) / exp
        errors.append(err)
        by_lang.setdefault(m["lang"], []).append(err)
        if hit < sum(gold_ids.values()) or err > 0.25:
            misses.append({"id": m["id"], "text": m["text"], "expected": dict(gold_ids), "got": dict(pred_ids),
                           "unmatched": [p["input"] for p in pred if not p["matched"]], "kcal_error": round(err, 3)})
    return {
        "meals_scored": len(scored),
        "meals_total": len(meals),
        "item_precision": round(tp / n_pred, 3) if n_pred else None,
        "item_recall": round(tp / n_gold, 3) if n_gold else None,
        "portion_within_10pct": round(portion_ok / n_gold, 3) if n_gold else None,
        "kcal_mape": round(statistics.mean(errors), 3) if errors else None,
        "kcal_median_ape": round(statistics.median(errors), 3) if errors else None,
        "kcal_mape_by_lang": {k: round(statistics.mean(v), 3) for k, v in sorted(by_lang.items())},
        "misses": misses,
    }


def main() -> None:
    engine = sys.argv[sys.argv.index("--engine") + 1] if "--engine" in sys.argv else "rules"
    meals = json.loads((HERE / "meals.json").read_text(encoding="utf-8"))
    preds = predict(engine, meals)
    # "basic" was written alongside the alias list (same vocabulary); "hard" uses phrasings and spellings the
    # alias list was not built from, and the aliases were frozen before it was scored.
    result = {"engine": engine, **{split: score([m for m in meals if m["split"] == split], preds) for split in ("basic", "hard")}}
    if engine != "rules":
        cache = json.loads((RUNS / f"{engine}.json").read_text(encoding="utf-8")) if (RUNS / f"{engine}.json").exists() else {}
        result["models"] = dict(Counter(v["model"] for v in cache.values()))
    out = HERE / f"results_{engine}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {k: ({kk: vv for kk, vv in v.items() if kk != "misses"} if isinstance(v, dict) and "misses" in v else v) for k, v in result.items()}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"details of misses in {out.name}")


if __name__ == "__main__":
    main()

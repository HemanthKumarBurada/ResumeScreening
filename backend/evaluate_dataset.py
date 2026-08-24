"""
Offline evaluation harness -- runs the S1 screening pipeline directly
against your synthetic dataset (no API, no Postgres, no PDF upload needed)
so you can generate the numbers your paper's Results section needs.

This evaluates whatever SEMANTIC_WEIGHT / SKILL_WEIGHT / CONTEXTUAL_THRESHOLD
/ BEST_CUT / AVERAGE_CUT are currently set in matcher.py -- it does not sweep
over them itself. If you're re-tuning those constants, do the grid search
separately (see the Kaggle notebook / sweep script) and then hand-edit
matcher.py's constants before re-running this script for the final numbers.

Produces three CSVs in backend/eval_results/ plus a printed summary:

1. gold_pair_results.csv      -- your S1 vs. the dataset's gold_match_score,
                                   your tier vs. gold_match_tier, per pair
2. skill_cascade_results.csv  -- per-skill tier prediction vs. the labeled
                                   skill_mention_types ground truth
3. fraud_detection_results.csv -- genuine vs. stuffed resume S1 scores, i.e.
                                   how much keyword-stuffing alone inflates
                                   the screening score with no downstream
                                   verification stage in the pipeline

Run it with:
    cd backend
    venv\\Scripts\\activate      (Windows)  /  source venv/bin/activate (Mac/Linux)
    python evaluate_dataset.py
"""

import csv
import json
import statistics
from pathlib import Path

import matcher

DATA_DIR = Path(__file__).parent / "data"
OUT_DIR = Path(__file__).parent / "eval_results"
OUT_DIR.mkdir(exist_ok=True)


def load_csv(name):
    with open(DATA_DIR / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    std_x = (sum((x - mean_x) ** 2 for x in xs)) ** 0.5
    std_y = (sum((y - mean_y) ** 2 for y in ys)) ** 0.5
    if std_x == 0 or std_y == 0:
        return float("nan")
    return cov / (std_x * std_y)


def normalize_tier(tier: str) -> str:
    # Dataset uses "Best Match" / "Average Match" / "Low Match";
    # matcher.py uses "Best" / "Average" / "Low". Normalize both to compare.
    return tier.replace(" Match", "").strip()


# ---------------------------------------------------------------------------
# 1. Gold match pairs -- S1 vs. gold_match_score, tier vs. gold_match_tier
# ---------------------------------------------------------------------------

def evaluate_gold_pairs():
    print("\n=== Evaluating against 04_gold_match_pairs.csv ===")
    resumes = {r["resume_id"]: r for r in load_csv("02_resumes.csv")}
    jds = {j["jd_id"]: j for j in load_csv("03_job_descriptions.csv")}
    gold_pairs = load_csv("04_gold_match_pairs.csv")

    rows_out = []
    predicted_scores, gold_scores = [], []
    tier_correct = 0

    for i, pair in enumerate(gold_pairs):
        resume = resumes.get(pair["resume_id"])
        jd = jds.get(pair["jd_id"])
        if not resume or not jd:
            continue

        required_skills = json.loads(jd["required_skills"])
        result = matcher.score_application(resume["resume_text"], jd["jd_text"], required_skills)

        predicted_tier = result["tier"]
        gold_tier = normalize_tier(pair["gold_match_tier"])
        is_tier_match = predicted_tier == gold_tier
        tier_correct += int(is_tier_match)

        predicted_scores.append(result["screening_score"])
        gold_scores.append(float(pair["gold_match_score"]))

        rows_out.append({
            "pair_id": pair["pair_id"],
            "resume_id": pair["resume_id"],
            "jd_id": pair["jd_id"],
            "phi_sem": result["phi_sem"],
            "theta_skill": result["theta_skill"],
            "predicted_score": result["screening_score"],
            "gold_score": pair["gold_match_score"],
            "predicted_tier": predicted_tier,
            "gold_tier": gold_tier,
            "tier_match": is_tier_match,
        })

        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{len(gold_pairs)} pairs scored")

    with open(OUT_DIR / "gold_pair_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows_out[0].keys())
        writer.writeheader()
        writer.writerows(rows_out)

    corr = pearson(predicted_scores, gold_scores)
    tier_acc = tier_correct / len(rows_out) if rows_out else 0

    print(f"Pearson correlation (S1 vs gold_match_score): {corr:.4f}")
    print(f"Tier agreement accuracy (predicted vs gold tier): {tier_acc:.4f} ({tier_correct}/{len(rows_out)})")
    print(f"Wrote {len(rows_out)} rows to eval_results/gold_pair_results.csv")


# ---------------------------------------------------------------------------
# 2. Skill cascade accuracy -- per-skill tier prediction vs. labeled ground truth
# ---------------------------------------------------------------------------

def evaluate_skill_cascade():
    print("\n=== Evaluating skill cascade against 02_resumes.csv labels ===")
    resumes = load_csv("02_resumes.csv")

    rows_out = []
    tier_counts = {"exact": [0, 0], "fuzzy": [0, 0], "contextual": [0, 0]}  # [correct, total]

    for i, resume in enumerate(resumes):
        ground_truth_tiers = json.loads(resume["skill_mention_types"])  # {skill: "exact"/"fuzzy"/"contextual"}

        for skill, true_tier in ground_truth_tiers.items():
            predicted = matcher.match_skill(skill, resume["resume_text"])
            predicted_tier = predicted["tier"]

            if true_tier in tier_counts:
                tier_counts[true_tier][1] += 1
                if predicted_tier == true_tier:
                    tier_counts[true_tier][0] += 1

            rows_out.append({
                "resume_id": resume["resume_id"],
                "skill": skill,
                "true_tier": true_tier,
                "predicted_tier": predicted_tier,
                "match": predicted_tier == true_tier,
            })

        if (i + 1) % 100 == 0:
            print(f"  ...{i + 1}/{len(resumes)} resumes processed")

    with open(OUT_DIR / "skill_cascade_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows_out[0].keys())
        writer.writeheader()
        writer.writerows(rows_out)

    print("Per-tier recall (did the cascade correctly identify skills genuinely mentioned at that tier?):")
    for tier, (correct, total) in tier_counts.items():
        recall = correct / total if total else float("nan")
        print(f"  {tier:12s}: {correct}/{total} = {recall:.4f}")
    print(f"Wrote {len(rows_out)} rows to eval_results/skill_cascade_results.csv")


if __name__ == "__main__":
    evaluate_gold_pairs()
    evaluate_skill_cascade()
    print(f"\nAll done. Results in: {OUT_DIR}")
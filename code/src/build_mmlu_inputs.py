"""Build the frozen MMLU replication input set (cross-domain arm).

Reviewers asked for a replication on a substantially different domain. This builds
the medical-decision arm from MMLU (MIT licence, no personal data): the two clinical
subsets, cast into exactly the shape the existing orchestrator already consumes, so
collection, exact-resume and freezing logic are reused unchanged.

Two deliberate choices:

  * Choice order is shuffled deterministically per item. MMLU's raw answer key is
    skewed (option D is 37% of answers), so a model could beat chance on position
    alone. The shuffle is seeded from the item's own content hash, so it is stable
    across machines and reruns, and identical for every agent and configuration --
    all five agents must see the same item or the paired design breaks.

  * Items are mapped onto the (ticker, date) slots the orchestrator uses. The item is
    the ticker analogue: it is the independent unit, and the cluster bootstrap
    resamples it. date is a constant placeholder because agent.py validates it as an
    ISO date for the no-lookahead check.

Usage:  python code/src/build_mmlu_inputs.py --raw /tmp/mmlu/raw.json
"""
from __future__ import annotations
import argparse, hashlib, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-01-01"          # constant analysis date; MMLU items are not time-indexed
ASOF = "2025-12-31"          # must be strictly before DATE (no-lookahead check)
LETTERS = ["A", "B", "C", "D"]
PREFIX = {"professional_medicine": "MED", "clinical_knowledge": "CLIN"}


def item_id(subject: str, n: int) -> str:
    return f"{PREFIX[subject]}{n:04d}"


def shuffled(choices: list[str], answer: int, key: str) -> tuple[list[str], int]:
    """Deterministic per-item shuffle; returns (choices, new answer index)."""
    order = list(range(len(choices)))
    random.Random(hashlib.sha256(key.encode()).hexdigest()).shuffle(order)
    return [choices[i] for i in order], order.index(answer)


def render(question: str, choices: list[str]) -> str:
    opts = "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(choices))
    return f"{question.strip()}\n\n{opts}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="JSON list of {subject,question,choices,answer}")
    ap.add_argument("--out", default="data/inputs_mmlu")
    a = ap.parse_args()

    raw = json.loads(Path(a.raw).read_text(encoding="utf-8"))
    outdir = ROOT / a.out
    outdir.mkdir(parents=True, exist_ok=True)

    truth, counts, seen = {}, {l: 0 for l in LETTERS}, set()
    per_subject: dict[str, int] = {}
    for r in raw:
        subj = r["subject"]
        if len(r["choices"]) != len(LETTERS):
            print(f"ERROR: item with {len(r['choices'])} choices; expected {len(LETTERS)}")
            return 1
        per_subject[subj] = per_subject.get(subj, 0) + 1
        iid = item_id(subj, per_subject[subj])
        if iid in seen:
            print(f"ERROR: duplicate item id {iid}"); return 1
        seen.add(iid)
        ch, ans = shuffled(r["choices"], int(r["answer"]), iid + r["question"])
        letter = LETTERS[ans]
        counts[letter] += 1
        (outdir / f"{iid}_{DATE}.json").write_text(json.dumps(
            {"asof": ASOF, "text": render(r["question"], ch), "subject": subj},
            ensure_ascii=False), encoding="utf-8")
        truth[iid] = {"subject": subj, "answer": letter}

    (ROOT / "data" / "mmlu_ground_truth.json").write_text(
        json.dumps(truth, indent=1, sort_keys=True), encoding="utf-8")

    h = hashlib.sha256()
    for f in sorted(outdir.glob("*.json")):
        h.update(f.name.encode()); h.update(f.read_bytes())
    manifest = {"n_items": len(truth), "per_subject": per_subject, "date": DATE, "asof": ASOF,
                "labels": LETTERS, "answer_distribution": counts,
                "inputs_sha256": h.hexdigest(),
                "ground_truth_sha256": hashlib.sha256(
                    (ROOT / "data" / "mmlu_ground_truth.json").read_bytes()).hexdigest(),
                "source": "cais/mmlu (MIT); subsets professional_medicine, clinical_knowledge",
                "note": "choice order shuffled deterministically per item; see build_mmlu_inputs.py"}
    (ROOT / "data" / "mmlu_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    print(f"   wrote {len(truth)} items to {a.out}")
    print(f"   per subject       : {per_subject}")
    print(f"   answer letters    : {counts}")
    print(f"   inputs sha256     : {manifest['inputs_sha256'][:32]}…")
    print(f"   ground truth sha  : {manifest['ground_truth_sha256'][:32]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())

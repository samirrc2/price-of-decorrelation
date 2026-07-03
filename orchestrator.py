"""INDEPENDENT-mode orchestrator.

Iterates the fixed grid (config x ticker x date x run x agent), issuing one fresh
API call per agent — no shared context, no caching, no cross-agent state. Logs
every call to runs.csv and enforces the hard spend cap in real time.

Design guarantees
-----------------
* Deterministic order & resumable: completed (config,ticker,date,run,agent) rows
  in an existing runs.csv are skipped, so a killed run resumes exactly.
* No lookahead: snippet as-of date is asserted strictly before the analysis date.
* Cutoff guard: refuses to start if any analysis date <= any model knowledge
  cutoff, or if a date is too recent for the forward-return proxy to have realised.
* Spend cap: before each call it projects worst-case marginal cost; if cumulative
  + projection would breach (cap - margin) it STOPS and reports.

Usage:  python orchestrator.py            # run / resume
        python orchestrator.py --dry-run  # validate config + grid, no API calls
"""
from __future__ import annotations
import argparse
import csv
import json
import hashlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

import agent as agentmod
import secrets as secretstore

_HERE = Path(__file__).resolve().parent
_CACHE_DIR = _HERE / "cache" / "responses"
_RESULTS_DIR = _HERE / "results" / "raw"

CSV_FIELDS = [
    "phase", "config", "ticker", "date", "run_idx", "run_seed", "seed", "seed_mode",
    "agent_idx", "attempt",
    "model", "api_model", "provider", "timestamp_utc", "prompt_hash",
    "snippet_source", "snippet_asof",
    "direction", "conviction", "rationale",
    "input_tokens", "output_tokens", "cost_usd", "cached",
    "ok", "error", "raw_response",
]


def derive_agent_seed(seed_mode, master, run_seed, config, ticker, date, agent_idx):
    """Return the seed actually sent for one agent call.

    per_agent : a unique, reproducible seed per (run, cell, agent) — the corrected
                estimand: 5 INDEPENDENT draws per ensemble, not one draw x5.
    per_run   : legacy — all 5 agents in a run share the run seed (correlated draws).
    none      : no seed sent; provider samples freely (max independence, non-reproducible).
    """
    if seed_mode == "none":
        return None
    if seed_mode == "per_run":
        return run_seed
    # per_agent (default). Mask to a positive signed 32-bit int: xAI (and some other
    # providers) reject seeds outside the i32 range.
    raw = f"{master}|{run_seed}|{config}|{ticker}|{date}|{agent_idx}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


def _response_cache_key(mcfg, prompt_hash, seed, temperature):
    raw = f"{mcfg['provider']}|{mcfg['api_model']}|{prompt_hash}|{seed}|{temperature}|" \
          f"{mcfg.get('max_tokens',256)}|{mcfg.get('reasoning_effort','')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _cache_get(key):
    import json
    f = _CACHE_DIR / f"{key}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return None
    return None


def _cache_put(key, payload):
    import json
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (_CACHE_DIR / f"{key}.json").write_text(json.dumps(payload, indent=2))


def _store_result(mcfg, row):
    """Per-model result storage: results/raw/<provider>/<model>/<config>_<ticker>_<date>_r<run>_a<agent>.json"""
    import json
    d = _RESULTS_DIR / mcfg["provider"] / mcfg["api_model"]
    d.mkdir(parents=True, exist_ok=True)
    name = (f"{row['config']}_{row['ticker']}_{row['date']}_r{row['run_idx']}"
            f"_a{row['agent_idx']}_try{row.get('attempt', 1)}.json")
    (d / name).write_text(json.dumps(row, indent=2))


def load_config() -> dict:
    return yaml.safe_load((_HERE / "config.yaml").read_text())


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_dates(cfg: dict, today: date, dates=None) -> list[str]:
    problems = []
    fwd = int(cfg["forward_return_days"])
    # rough calendar buffer for `fwd` trading days (~1.4x)
    min_gap_days = int(fwd * 1.5) + 2
    models = cfg["models"]
    for d in (dates if dates is not None else cfg["dates"]):
        dd = date.fromisoformat(d)
        for mname, m in models.items():
            cut = date.fromisoformat(m["knowledge_cutoff"])
            if dd <= cut:
                problems.append(
                    f"date {d} is not strictly after {mname} knowledge_cutoff "
                    f"{m['knowledge_cutoff']} (would risk memorised answers)")
        gap = (today - dd).days
        if gap < min_gap_days:
            problems.append(
                f"date {d} is only {gap} calendar days before today ({today}); "
                f"need >= ~{min_gap_days} for {fwd} trading-day forward return to realise")
    return problems


def price_of(model_cfg: dict, in_tok: int, out_tok: int) -> float:
    return (in_tok / 1e6) * model_cfg["price_in"] + (out_tok / 1e6) * model_cfg["price_out"]


def worst_case_cost(model_cfg: dict, est_in_tok: int) -> float:
    return price_of(model_cfg, est_in_tok, int(model_cfg.get("max_tokens", 256)))


# --------------------------------------------------------------------------- #
# Resume support
# --------------------------------------------------------------------------- #
def load_done(runs_csv: Path) -> set[tuple]:
    done = set()
    if not runs_csv.exists():
        return done
    with runs_csv.open() as f:
        for row in csv.DictReader(f):
            if row.get("ok") == "True":
                done.add((row["config"], row["ticker"], row["date"],
                          int(row["run_idx"]), int(row["agent_idx"])))
    return done


def append_row(runs_csv: Path, row: dict) -> None:
    new = not runs_csv.exists()
    with runs_csv.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="validate only, no API calls")
    ap.add_argument("--today", default=None, help="override today (YYYY-MM-DD) for gates")
    ap.add_argument("--phase", choices=["minipilot", "full"], default="full",
                    help="minipilot (Phase 1.5 gate) or full (Phase 2 single execution)")
    ap.add_argument("--concurrency", type=int, default=None,
                    help="parallel worker threads (default: config.concurrency or 1). "
                         "Order-independent: does NOT affect analysis determinism.")
    args = ap.parse_args()

    cfg = load_config()
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    phase = args.phase

    # Phase selects the grid, caps, and output paths.
    if phase == "minipilot":
        mp = cfg["minipilot"]
        tickers = mp["tickers"]
        dates = mp["dates"]
        n_runs = int(mp["runs"])
        cap = float(mp["spend_cap_usd"])
        runs_csv = _HERE / mp["paths"]["runs_csv"]
        ledger_path = _HERE / mp["paths"]["spend_ledger"]
    else:
        tickers = cfg["tickers"]
        dates = cfg["dates"]
        n_runs = int(cfg["runs"])
        cap = float(cfg["spend_cap_usd"])
        runs_csv = _HERE / cfg["paths"]["runs_csv"]
        ledger_path = _HERE / cfg["paths"]["spend_ledger"]
    runs_csv.parent.mkdir(parents=True, exist_ok=True)
    margin = float(cfg["stop_margin_usd"])
    max_retries = int(cfg.get("max_retries", 3))
    midrun_at = float(cfg.get("midrun_report_at", 0.5))

    problems = validate_dates(cfg, today, dates)
    if problems:
        print("CONFIG VALIDATION FAILED:")
        for p in problems:
            print("  -", p)
        print("\nFix config.yaml (dates / knowledge_cutoff) and retry.")
        return 2

    inputs_dir = _HERE / cfg["paths"]["inputs_dir"]

    # Build the deterministic call list (all configs).
    calls = []
    config_names = list(cfg["configs"].keys())
    for config_name in config_names:
        slots = cfg["configs"][config_name]
        for ticker in tickers:
            for d in dates:
                for run_idx, seed in enumerate(cfg["seeds"][:n_runs]):
                    for agent_idx, slot in enumerate(slots):
                        calls.append((config_name, ticker, d, run_idx, seed, agent_idx, slot["model"]))

    total = len(calls)
    print(f"PHASE: {phase} | Grid: {total} calls "
          f"({len(tickers)} tickers x {len(dates)} dates x {len(config_names)} configs "
          f"x {n_runs} runs x 5 agents).")

    # Pre-flight cost projection using a token estimate (full grid, worst case out).
    est_in = 320  # ~ system+user prompt tokens; refined below per real call
    proj = 0.0
    for (_c, _t, _d, _r, _s, _a, model) in calls:
        proj += worst_case_cost(cfg["models"][model], est_in)
    print(f"Worst-case projected cost for full grid: ${proj:,.2f}  (cap ${cap:.2f})")

    if args.dry_run:
        secretstore  # noqa: ensure importable
        print("\nDRY RUN OK — config valid, no API calls made.")
        if proj > cap:
            print(f"WARNING: worst-case projection ${proj:.2f} exceeds cap ${cap:.2f}; "
                  f"the run will STOP partway. Reduce grid or raise cap.")
        return 0

    done = load_done(runs_csv)
    if done:
        print(f"Resuming: {len(done)} calls already logged, will skip them.")

    # Verify keys for every provider used, up front, before spending.
    providers = {cfg["models"][m]["provider"] for (*_x, m) in calls}
    for prov in providers:
        secretstore.get_key(prov)  # raises with a clear message if missing

    seed_mode = str(cfg.get("seed_mode", "per_agent"))
    master = int(cfg["seed_master"])
    workers = args.concurrency or int(cfg.get("concurrency", 1))
    workers = max(1, workers)
    print(f"Seed mode: {seed_mode} "
          f"({'INDEPENDENT per-agent draws' if seed_mode=='per_agent' else seed_mode}). "
          f"Concurrency: {workers} worker(s).")

    todo = [c for c in calls if (c[0], c[1], c[2], c[3], c[5]) not in done]
    remaining = len(todo)

    # shared state (thread-safe). Execution order does NOT affect analysis (analyze.py
    # is order-independent); concurrency is purely a wall-clock optimization.
    st = {"cum": 0.0, "n_done": 0, "n_fail": 0, "stop": False}
    lock_spend = threading.Lock()
    lock_io = threading.Lock()
    temp = float(cfg["temperature"])

    def process(slot):
        (config_name, ticker, d, run_idx, run_seed, agent_idx, model) = slot
        mcfg = cfg["models"][model]
        seed = derive_agent_seed(seed_mode, master, run_seed, config_name, ticker, d, agent_idx)
        snip = agentmod.load_or_build_snippet(ticker, d, inputs_dir)
        user = agentmod.build_prompt(ticker, snip)
        ph = agentmod.prompt_hash(agentmod.SYSTEM_PROMPT, user)
        use_cache = seed is not None
        ckey = _response_cache_key(mcfg, ph, seed, temp) if use_cache else None
        cached_hit = _cache_get(ckey) if use_cache else None

        attempts = []
        if cached_hit is not None:
            try:
                dec = agentmod.parse_strict(cached_hit["raw"])
                res = agentmod.AgentResult(True, dec, cached_hit["raw"],
                                           cached_hit["in_tok"], cached_hit["out_tok"], None, ph)
            except Exception as e:
                res = agentmod.AgentResult(False, None, cached_hit.get("raw", ""),
                                           cached_hit.get("in_tok", 0), cached_hit.get("out_tok", 0),
                                           f"parse(cached): {e}", ph)
            attempts.append((res, True, 1))
        else:
            wc = worst_case_cost(mcfg, est_in)
            with lock_spend:
                if st["stop"] or st["cum"] + wc > (cap - margin):
                    st["stop"] = True
                    return
            for attempt in range(1, max_retries + 2):
                res = agentmod.run_agent(mcfg, ticker, snip, temp, seed)
                with lock_spend:
                    st["cum"] += price_of(mcfg, res.input_tokens, res.output_tokens)
                if use_cache and res.ok and (res.raw_response or res.output_tokens):
                    _cache_put(ckey, {"raw": res.raw_response,
                                      "in_tok": res.input_tokens, "out_tok": res.output_tokens})
                attempts.append((res, False, attempt))
                if res.ok:
                    break

        with lock_io:
            for (res, is_cached, attempt) in attempts:
                cost = price_of(mcfg, res.input_tokens, res.output_tokens)
                row = {
                    "phase": phase, "config": config_name, "ticker": ticker, "date": d,
                    "run_idx": run_idx, "run_seed": run_seed, "seed": seed,
                    "seed_mode": seed_mode, "agent_idx": agent_idx, "attempt": attempt,
                    "model": model, "api_model": mcfg["api_model"], "provider": mcfg["provider"],
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "prompt_hash": res.prompt_hash,
                    "snippet_source": snip.source, "snippet_asof": snip.asof,
                    "direction": res.decision.direction if res.decision else "",
                    "conviction": res.decision.conviction if res.decision else "",
                    "rationale": res.decision.rationale if res.decision else "",
                    "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                    "cost_usd": round(cost, 6), "cached": is_cached,
                    "ok": res.ok, "error": res.error or "",
                    "raw_response": (res.raw_response or "").replace("\n", " ")[:2000],
                }
                append_row(runs_csv, row)
                _store_result(mcfg, row)
                if not res.ok:
                    st["n_fail"] += 1
                    tag = "retry" if attempt > 1 else "call"
                    print(f"  ! {config_name} {ticker} {d} run{run_idx} agent{agent_idx} "
                          f"({model}) {tag} {attempt} FAILED: {res.error}")
            st["n_done"] += 1
            nd = st["n_done"]
            ledger_path.write_text(json.dumps({
                "phase": phase, "cumulative_usd": round(st["cum"], 6),
                "slots_completed_this_session": nd,
                "attempt_failures_this_session": st["n_fail"],
                "cap_usd": cap, "updated": datetime.now(timezone.utc).isoformat(),
            }, indent=2))
            if remaining and nd == int(midrun_at * remaining):
                print(f"  === MID-RUN ({midrun_at:.0%}): {nd}/{remaining} slots, "
                      f"cumulative ${st['cum']:.4f} / cap ${cap:.2f} ===")
            if nd % 100 == 0:
                print(f"  ...{nd}/{remaining} slots, cumulative ${st['cum']:.4f}")

    if workers == 1:
        for slot in todo:
            if st["stop"]:
                break
            process(slot)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(process, todo))

    if st["stop"]:
        print(f"\nSTOP: spend cap ${cap:.2f} guard tripped; halted cleanly. "
              f"runs.csv holds all completed calls (resume by re-running).")
    print(f"\nDone this session: {st['n_done']}/{remaining} slots, {st['n_fail']} attempt-failures, "
          f"spend ${st['cum']:.4f} / cap ${cap:.2f}.")
    print(f"Raw log: {runs_csv}")
    print("Next: python analyze.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

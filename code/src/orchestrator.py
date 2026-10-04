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
import re
import sys
import threading
import time
from collections import Counter
try:
    import resource  # POSIX only; used to raise the open-file limit
except ImportError:
    resource = None
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

import agent as agentmod
import secrets as secretstore
import io_paths as _iopaths

_HERE = _iopaths.repo_root()
_CACHE_DIR = _HERE / "cache" / "responses"
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


class RateLimiter:
    """Global min-interval limiter: spaces requests to stay under an RPM cap.
    Shared across all worker threads for one provider."""
    def __init__(self, rpm):
        self.min_interval = (60.0 / rpm) if rpm and rpm > 0 else 0.0
        self.lock = threading.Lock()
        self.next_time = 0.0

    def acquire(self):
        if self.min_interval <= 0:
            return
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next_time)
            self.next_time = t + self.min_interval
            wait = t - now
        if wait > 0:
            time.sleep(wait)


def classify_error(err: str):
    """Classify a failed call. Returns (kind, retry_delay_seconds|None).
    kind: 'daily_quota' | 'rate_limit' | 'transient' | 'other'.
    A daily_quota (e.g. Gemini generate_requests_per_model_per_day, retryDelay ~5917s)
    must NOT be retried per-cell — the bucket won't refill for hours."""
    e = err or ""
    el = e.lower()
    delay = None
    m = re.search(r"retrydelay['\":\s]+(\d+(?:\.\d+)?)s", el)
    if m:
        delay = float(m.group(1))
    else:
        m2 = re.search(r"retry in\s+(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", el)
        if m2 and any(m2.groups()):
            delay = int(m2.group(1) or 0) * 3600 + int(m2.group(2) or 0) * 60 + float(m2.group(3) or 0)
    if any(k in el for k in ("per_day", "perday", "requests_per_model_per_day", "per-day", "requests_per_day")):
        return "daily_quota", delay
    if "resource_exhausted" in el and delay and delay > 300:
        return "daily_quota", delay
    if "429" in e or "rate limit" in el or "rate_limit" in el or "resource_exhausted" in el or "quota" in el:
        return "rate_limit", delay
    if any(k in el for k in ("connection error", "timeout", "timed out", "503", "unavailable", "502")):
        return "transient", delay
    return "other", delay


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
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (_CACHE_DIR / f"{key}.json").write_text(json.dumps(payload, indent=2))
    except OSError:
        pass  # best-effort cache; never block a logged result


def _store_result(mcfg, row):
    """Per-call JSON under data/raw/YYYYMMDD/<provider>/<model>/... (gitignored)."""
    import json
    d = _iopaths.raw_dump_dir() / mcfg["provider"] / mcfg["api_model"]
    d.mkdir(parents=True, exist_ok=True)
    name = (f"{row['config']}_{row['ticker']}_{row['date']}_r{row['run_idx']}"
            f"_a{row['agent_idx']}_try{row.get('attempt', 1)}.json")
    (d / name).write_text(json.dumps(row, indent=2))


def load_config(path: str = "configs/config.yaml") -> dict:
    return yaml.safe_load(_iopaths.resolve_config_path(path).read_text())


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
    ap.add_argument("--allow-over-quota", action="store_true",
                    help="proceed even if a model's planned calls exceed its daily_limit "
                         "(use after enabling billing / a higher tier).")
    ap.add_argument("--config", default="configs/config.yaml",
                    help="config file to use (e.g. configs/config_control.yaml for the "
                         "HET-SameTier confound control). Keeps control runs separate.")
    ap.add_argument("--temperature", type=float, default=None,
                    help="override the sampling temperature for this run (e.g. the "
                         "T-sweep robustness study). Default: config.temperature.")
    ap.add_argument("--runs-csv", default=None, dest="runs_csv_override",
                    help="override the output runs.csv path (keeps a T-sweep or other "
                         "side-run fully separate from the frozen study file).")
    ap.add_argument("--data-date", default=None,
                    help="YYYYMMDD collection folder under data/<kind>/ (default: today UTC). "
                         "Creates the folder and points data/<kind>/latest at it. "
                         "Ignored when --runs-csv is set to an absolute/fully-dated path.")
    ap.add_argument("--dataset-kind", default=None,
                    help="Dataset kind (confirmatory, control, minipilot, "
                         "temperature_robustness_small). Default inferred from --config/--phase.")
    ap.add_argument("--max-calls", type=int, default=None,
                    help="Cap the planned call list to the first N slots (deterministic "
                         "prefix of the full grid). Useful for scratch collections "
                         "(e.g. 48000). Default: full grid.")
    ap.add_argument("--fresh", action="store_true",
                    help="Start a brand-new collection folder (unique stamp) with an "
                         "empty runs.csv — do not resume any existing log.")
    args = ap.parse_args()

    cfg = load_config(args.config)
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    phase = args.phase

    def _infer_kind() -> str:
        if args.dataset_kind:
            return args.dataset_kind
        cfg_name = Path(args.config).name.lower()
        if "control" in cfg_name:
            return "control"
        if "temp" in cfg_name:
            return "temperature_robustness_small"
        if phase == "minipilot":
            return "minipilot"
        return "confirmatory"

    kind = _infer_kind()

    # Phase selects the grid and caps.
    if phase == "minipilot":
        mp = cfg["minipilot"]
        tickers = mp["tickers"]
        dates = mp["dates"]
        n_runs = int(mp["runs"])
        cap = float(mp["spend_cap_usd"])
    else:
        tickers = cfg["tickers"]
        dates = cfg["dates"]
        n_runs = int(cfg["runs"])
        cap = float(cfg["spend_cap_usd"])

    # Collection outputs: dated folder (never overwrite an older vintage).
    if args.runs_csv_override:
        raw = Path(args.runs_csv_override)
        name = raw.name
        # Paths through latest/ or without a YYYYMMDD segment go into a collection dir.
        if (not raw.is_absolute()) and (
            "latest" in raw.parts or _iopaths.infer_data_date(raw) is None
        ):
            coll = _iopaths.new_collection_dir(kind, args.data_date, fresh=args.fresh)
            runs_csv = coll / name
        else:
            runs_csv = raw if raw.is_absolute() else _iopaths.resolve_data_path(raw)
        ledger_path = runs_csv.with_name(runs_csv.stem + "_ledger.json")
    else:
        # New / resumed collection. --fresh → unique stamp + empty log (scratch runs).
        if args.dry_run:
            day = args.data_date or (
                _iopaths.utc_now_run_stamp() if args.fresh else _iopaths.utc_today_yyyymmdd()
            )
            coll = _iopaths.kind_root(kind) / day
            coll.mkdir(parents=True, exist_ok=True)
            # dry-run: do not flip data/<kind>/latest
        else:
            coll = _iopaths.new_collection_dir(kind, args.data_date, fresh=args.fresh)
        runs_csv = coll / "runs.csv"
        ledger_path = coll / "spend_ledger.json"

    if args.fresh and runs_csv.exists() and runs_csv.stat().st_size > 0:
        # Unique stamp should avoid this; if not, refuse rather than resume.
        print(f"ERROR: --fresh but {runs_csv} already has data. Refusing to resume.")
        return 2

    print(f"Collection output: {runs_csv}"
          f"{'  [FRESH — start from beginning]' if args.fresh else ''}")
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

    inputs_dir = _iopaths.resolve_data_path(cfg["paths"]["inputs_dir"])

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

    if args.max_calls is not None:
        if args.max_calls <= 0:
            print("ERROR: --max-calls must be positive")
            return 2
        if args.max_calls < len(calls):
            print(f"Scratch budget: {args.max_calls} calls starting from the beginning "
                  f"of the study grid (slots 1..{args.max_calls} of {len(calls)}).")
            calls = calls[: args.max_calls]
        else:
            print(f"--max-calls {args.max_calls} ≥ full grid ({len(calls)}); using full grid.")

    total = len(calls)
    print(f"PHASE: {phase} | Grid: {total} calls "
          f"({len(tickers)} tickers x {len(dates)} dates x {len(config_names)} configs "
          f"x {n_runs} runs x 5 agents"
          f"{'' if args.max_calls is None else f'; max-calls={args.max_calls}'}).")

    # ---- PRE-FLIGHT daily-quota check ----
    # Count only REMAINING (not-yet-completed) calls per model, so a backfill/resume
    # is judged on what it will actually send today, not the whole grid.
    daily_limits = cfg.get("daily_limits", {}) or {}
    _done_pre = load_done(runs_csv)
    _remaining = [c for c in calls if (c[0], c[1], c[2], c[3], c[5]) not in _done_pre]
    planned = Counter(c[6] for c in _remaining)  # by model key
    if _done_pre:
        print(f"Pre-flight: {len(_done_pre)} calls already done; {len(_remaining)} remaining.")
    over = []
    for mkey, n_planned in planned.items():
        lim = daily_limits.get(mkey) or daily_limits.get(cfg["models"][mkey]["api_model"])
        if lim and n_planned > lim:
            over.append((mkey, n_planned, lim))
    if over:
        print("\nPRE-FLIGHT QUOTA WARNING — planned calls exceed provider daily limits:")
        for mkey, n_planned, lim in over:
            print(f"  - {mkey}: {n_planned} planned > {lim}/day  (short by {n_planned - lim})")
        if not args.allow_over_quota:
            print("\nABORTING before spending. Options: raise the provider's tier/billing, "
                  "shrink the grid, or pass --allow-over-quota to run anyway (some cells will "
                  "be DEFERRED for backfill once the quota resets).")
            return 3
        print("  --allow-over-quota set: proceeding; over-quota cells will be deferred.\n")

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

    # Raise the open-file limit so concurrent HTTP sockets + cache writes don't hit
    # macOS's low default (256).
    if resource is not None:
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            resource.setrlimit(resource.RLIMIT_NOFILE, (min(max(soft, 8192), hard), hard))
        except Exception:
            pass

    seed_mode = str(cfg.get("seed_mode", "per_agent"))
    master = int(cfg["seed_master"])
    workers = args.concurrency or int(cfg.get("concurrency", 1))
    workers = max(1, workers)
    rpm_limits = cfg.get("rpm_limits", {}) or {}
    limiters = {prov: RateLimiter(rpm_limits.get(prov, 0)) for prov in providers}
    if rpm_limits:
        print(f"Rate limits (RPM): {rpm_limits}")
    print(f"Seed mode: {seed_mode} "
          f"({'INDEPENDENT per-agent draws' if seed_mode=='per_agent' else seed_mode}). "
          f"Concurrency: {workers} worker(s).")

    todo = [c for c in calls if (c[0], c[1], c[2], c[3], c[5]) not in done]
    remaining = len(todo)

    # shared state (thread-safe). Execution order does NOT affect analysis (analyze.py
    # is order-independent); concurrency is purely a wall-clock optimization.
    st = {"cum": 0.0, "n_done": 0, "n_fail": 0, "stop": False,
          "exhausted": set(), "deferred": 0}  # exhausted: models that hit a daily quota
    lock_spend = threading.Lock()
    lock_io = threading.Lock()
    temp = float(args.temperature) if args.temperature is not None else float(cfg["temperature"])
    print(f"Sampling temperature: {temp}"
          + ("  (CLI override)" if args.temperature is not None else "  (from config)"))

    def process(slot):
        try:
            _process(slot)
        except Exception as e:  # never let one slot kill the whole pool
            with lock_io:
                print(f"  !! worker error on {slot[:4]} {slot[5:]}: {type(e).__name__}: {e}")

    def _process(slot):
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
                model_dead = model in st["exhausted"]
            if model_dead:
                # Circuit breaker: this model already hit a daily quota. Do NOT call —
                # defer for backfill (fail-fast, no wasted spend).
                res = agentmod.AgentResult(False, None, "", 0, 0,
                                           f"DEFERRED_DAILY_QUOTA: {model}", ph)
                attempts.append((res, False, 1))
            else:
                lim = limiters.get(mcfg["provider"])
                for attempt in range(1, max_retries + 2):
                    if lim:
                        lim.acquire()
                    res = agentmod.run_agent(mcfg, ticker, snip, temp, seed)
                    with lock_spend:
                        st["cum"] += price_of(mcfg, res.input_tokens, res.output_tokens)
                    if res.ok:
                        if use_cache and (res.raw_response or res.output_tokens):
                            _cache_put(ckey, {"raw": res.raw_response,
                                              "in_tok": res.input_tokens, "out_tok": res.output_tokens})
                        attempts.append((res, False, attempt))
                        break
                    kind, delay = classify_error(res.error)
                    if kind == "daily_quota":
                        # per-DAY exhaustion: stop retrying, trip the breaker, defer.
                        with lock_spend:
                            st["exhausted"].add(model)
                        res = agentmod.AgentResult(
                            False, None, res.raw_response, res.input_tokens, res.output_tokens,
                            f"DEFERRED_DAILY_QUOTA: {model} (retry~{int(delay) if delay else '?'}s)", ph)
                        attempts.append((res, False, attempt))
                        break
                    attempts.append((res, False, attempt))
                    if attempt <= max_retries:
                        # adaptive backoff: longer for rate-limit/transient
                        time.sleep(min(30.0, (3.0 if kind in ("rate_limit", "transient") else 0.4)
                                       * (2 ** (attempt - 1))))
                    else:
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
                    if (res.error or "").startswith("DEFERRED"):
                        st["deferred"] += 1
                        if st["deferred"] in (1,) or st["deferred"] % 200 == 0:
                            print(f"  ~ DEFERRED (daily quota) — {model}; {st['deferred']} cells "
                                  f"queued for backfill. Not retrying today.")
                    else:
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

    # ---- honest run manifest (every session stamped) ----
    manifest = {
        "phase": phase,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "runs_csv": str(runs_csv),
        "slots_completed_this_session": st["n_done"],
        "attempt_failures_this_session": st["n_fail"],
        "deferred_this_session": st["deferred"],
        "models_exhausted_daily_quota": sorted(st["exhausted"]),
        "spend_usd_this_session": round(st["cum"], 6),
        "spend_cap_usd": cap,
    }
    (runs_csv.parent / "run_manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nDone this session: {st['n_done']}/{remaining} slots, {st['n_fail']} attempt-failures "
          f"({st['deferred']} DEFERRED for backfill), spend ${st['cum']:.4f} / cap ${cap:.2f}.")
    if st["exhausted"]:
        print(f"Models that hit a DAILY quota (backfill after reset / higher tier): "
              f"{sorted(st['exhausted'])}")
        print("  -> re-run the same command later to fill DEFERRED cells (resume skips completed).")
    print(f"Raw log: {runs_csv}   Manifest: run_manifest.json")
    print("Next: python analyze.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

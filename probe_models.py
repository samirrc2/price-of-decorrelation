"""Phase 0 — verify each selected model with ONE live test call.

Runs on the machine with live keys. For each model in config.yaml's registry it:
  - issues a single strict-JSON directional test call,
  - records the exact model string, raw response, latency, token usage,
  - captures a system fingerprint if the provider returns one,
  - probes the knowledge cutoff with a dated-event question (best-effort),
and rewrites the "Verified" block of model_manifest.md. Fails loudly on any
invalid model string so the manifest can't silently drift.

Cost: ~$0.10 total. No grid calls.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

import agent as agentmod
import secrets as secretstore

_HERE = Path(__file__).resolve().parent
MANIFEST = _HERE / "model_manifest.md"

TEST_SNIPPET = agentmod.Snippet(
    text="Headline: Test probe. Fundamentals: none.", asof="2025-01-01",
    source="probe")

CUTOFF_PROBE = ("In one short sentence, what is the most recent major world event "
                "you have reliable knowledge of, and its month and year?")


def probe_one(model_key, mcfg):
    out = {"model_key": model_key, "api_model": mcfg["api_model"],
           "provider": mcfg["provider"]}
    # 1) strict-JSON directional test
    t0 = time.time()
    res = agentmod.run_agent(mcfg, "AAPL", TEST_SNIPPET, 0.7, 12345)
    out["latency_s"] = round(time.time() - t0, 2)
    out["ok"] = res.ok
    out["error"] = res.error
    out["raw"] = (res.raw_response or "")[:300]
    out["in_tok"] = res.input_tokens
    out["out_tok"] = res.output_tokens
    out["fingerprint"] = _fingerprint(mcfg)
    # 2) cutoff probe (best-effort, free-text)
    try:
        txt, _, _ = agentmod.call_model(
            mcfg, "You answer in one short sentence.", CUTOFF_PROBE, 0.0, 1)
        out["cutoff_probe"] = txt.strip()[:200]
    except Exception as e:
        out["cutoff_probe"] = f"(probe failed: {type(e).__name__})"
    return out


def _fingerprint(mcfg):
    """Best-effort system_fingerprint capture (OpenAI/xAI expose it; Gemini doesn't)."""
    prov = mcfg["provider"]
    try:
        if prov in ("openai", "xai"):
            from openai import OpenAI
            if prov == "openai":
                client = OpenAI(api_key=secretstore.get_key("openai"))
            else:
                client = OpenAI(api_key=secretstore.get_key("xai"),
                                base_url="https://api.x.ai/v1")
            r = client.chat.completions.create(
                model=mcfg["api_model"], max_completion_tokens=16,
                messages=[{"role": "user", "content": "ok"}])
            return getattr(r, "system_fingerprint", None) or "(none returned)"
    except Exception as e:
        return f"(fingerprint n/a: {type(e).__name__})"
    return "(provider exposes no fingerprint)"


def main():
    cfg = yaml.safe_load((_HERE / "config.yaml").read_text())
    results = []
    for mk, mcfg in cfg["models"].items():
        print(f"probing {mk} ({mcfg['api_model']}) ...")
        results.append(probe_one(mk, mcfg))

    # rewrite the Verified block
    lines = ["## Verified (filled by probe_models.py)\n",
             f"_Probed {datetime.now(timezone.utc).isoformat()}_\n",
             "| model | ok | latency s | in/out tok | fingerprint | cutoff probe |",
             "|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| `{r['api_model']}` | {r['ok']} | {r['latency_s']} | "
                     f"{r['in_tok']}/{r['out_tok']} | {r['fingerprint']} | "
                     f"{r['cutoff_probe']} |")
    lines.append("\nRaw probe log: `model_probe_raw.json`.")

    text = MANIFEST.read_text()
    marker = "## Verified"
    text = text[:text.index(marker)] + "\n".join(lines) + "\n"
    MANIFEST.write_text(text)
    (_HERE / "model_probe_raw.json").write_text(json.dumps(results, indent=2))

    bad = [r["api_model"] for r in results if not r["ok"]]
    print(f"\nProbed {len(results)} models; {len(bad)} failed.")
    if bad:
        print("FAILED model strings (fix config.yaml before Phase 1):", bad)
        return 1
    print("All model strings valid. model_manifest.md Verified block updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

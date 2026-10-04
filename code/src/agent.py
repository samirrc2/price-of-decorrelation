"""Single agent: build a no-lookahead prompt, call one model, return STRICT JSON.

Provider router supports Anthropic out of the box; OpenAI / Google / xAI stubs
are wired so you can extend HET across vendors by editing config.yaml only.

Returns an AgentResult with parsed decision + exact token usage for costing.
"""
from __future__ import annotations
import json
import re
import hashlib
import threading
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

import os
import io_paths
from typing import Any

# One reused client per provider (thread-safe) — creating a client per call leaks
# sockets and exhausts the file-descriptor limit under concurrency.
_CLIENTS: dict[str, Any] = {}
_CLIENTS_LOCK = threading.Lock()


def _client(kind: str):
    with _CLIENTS_LOCK:
        c = _CLIENTS.get(kind)
        if c is not None:
            return c
        if kind == "openai":
            from openai import OpenAI
            c = OpenAI(api_key=secretstore.get_key("openai"), max_retries=0)
        elif kind == "xai":
            from openai import OpenAI
            c = OpenAI(api_key=secretstore.get_key("xai"),
                       base_url="https://api.x.ai/v1", max_retries=0)
        elif kind == "anthropic":
            from anthropic import Anthropic
            kwargs = {"api_key": secretstore.get_key("anthropic")}
            base = secretstore.get_base_url("anthropic")
            if base:
                kwargs["base_url"] = base
            c = Anthropic(**kwargs)
        elif kind == "gemini":
            from google import genai
            c = genai.Client(api_key=secretstore.get_key("google"))
        else:
            raise ValueError(f"unknown client kind {kind}")
        _CLIENTS[kind] = c
        return c

import secrets as secretstore  # local secrets.py (loads keys.env)

_HERE = io_paths.repo_root()

# The confirmatory study's label set and prompt are the defaults. The cross-domain
# replication arm (MMLU medical decisions) needs a different label vocabulary and
# prompt, so both are overridable by environment variable. Left unset, every value
# below is exactly what the frozen finance run used, so that path is byte-identical.
#
# Reusing BUY/HOLD/SELL for a clinical task was rejected deliberately: those tokens
# carry financial semantics that could leak into a medical judgement and confound
# the very comparison the replication is meant to make.
VALID_DIRECTIONS = set(
    os.environ.get("POD_LABELS", "BUY,HOLD,SELL").split(","))
PROMPT_FILE = os.environ.get("POD_PROMPT_FILE", "prompt_template.txt")


def _load_prompt_template():
    """Load the FROZEN prompt (hashed at Phase-1 freeze).
    Sections are delimited by [SYSTEM] and [USER]."""
    txt = (io_paths.data_root() / "configs" / PROMPT_FILE).read_text()
    sys_part = txt.split("[SYSTEM]", 1)[1].split("[USER]", 1)[0].strip()
    usr_part = txt.split("[USER]", 1)[1].strip()
    return sys_part, usr_part


SYSTEM_PROMPT, USER_TEMPLATE = _load_prompt_template()


# --------------------------------------------------------------------------- #
# Context snippets
# --------------------------------------------------------------------------- #
@dataclass
class Snippet:
    text: str
    asof: str          # ISO date; MUST predate the analysis date
    source: str        # "inputs_file" | "constructed_placeholder" | "constructed_filings"


def load_or_build_snippet(ticker: str, analysis_date: str, inputs_dir: Path) -> Snippet:
    """Prefer a human-provided snippet in inputs/<TICKER>_<DATE>.json.

    Expected JSON: {"headline": "...", "fundamentals": "...", "asof": "YYYY-MM-DD"}
    If absent, build a neutral, deterministic placeholder dated one day before the
    analysis date and FLAG it (source=constructed_placeholder) so downstream
    reporting can caveat that agents saw only a synthetic neutral prompt.
    """
    f = inputs_dir / f"{ticker}_{analysis_date}.json"
    if f.exists():
        d = json.loads(f.read_text())
        asof = d.get("asof") or _day_before(analysis_date)
        _assert_no_lookahead(asof, analysis_date, ticker)
        text = f"Headline: {d.get('headline','').strip()}\n" \
               f"Fundamentals: {d.get('fundamentals','').strip()}"
        return Snippet(text=text.strip(), asof=asof, source="inputs_file")

    # Fallback: neutral placeholder. Deliberately information-free so it does not
    # inject a fabricated view; dated the day before the analysis date.
    asof = _day_before(analysis_date)
    text = (
        f"No curated snippet supplied for {ticker}. Only public information "
        f"available on or before {asof} may be used. No new material headline "
        f"is provided; base the call on your prior knowledge of the company as of {asof}."
    )
    return Snippet(text=text, asof=asof, source="constructed_placeholder")


def _day_before(iso: str) -> str:
    from datetime import timedelta
    d = date.fromisoformat(iso) - timedelta(days=1)
    return d.isoformat()


def _assert_no_lookahead(asof: str, analysis_date: str, ticker: str) -> None:
    if date.fromisoformat(asof) >= date.fromisoformat(analysis_date):
        raise ValueError(
            f"LOOKAHEAD: snippet asof {asof} not strictly before analysis date "
            f"{analysis_date} for {ticker}."
        )


# --------------------------------------------------------------------------- #
# Prompt + hashing
# --------------------------------------------------------------------------- #
def build_prompt(ticker: str, snippet: Snippet) -> str:
    return USER_TEMPLATE.format(asof=snippet.asof, ticker=ticker, snippet=snippet.text)


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256((system + "\n\x1e\n" + user).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Strict JSON parsing
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    direction: str
    conviction: int
    rationale: str


def parse_strict(raw: str) -> Decision:
    """Parse model output into a validated Decision. Tolerant only of surrounding
    whitespace / accidental code fences; otherwise strict on schema."""
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", txt.strip())
    # Decode the FIRST JSON object and ignore any trailing data (some models,
    # e.g. Gemini in JSON mode, emit a second object or trailing text).
    start = txt.find("{")
    if start == -1:
        raise ValueError(f"No JSON object in response: {raw[:200]!r}")
    obj, _end = json.JSONDecoder().raw_decode(txt[start:])
    direction = str(obj["direction"]).strip().upper()
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"direction {direction!r} not in {VALID_DIRECTIONS}")
    conviction = int(obj["conviction"])
    if not (1 <= conviction <= 5):
        raise ValueError(f"conviction {conviction} out of range 1-5")
    rationale = str(obj["rationale"]).strip()
    if len(rationale.split()) > 30:
        rationale = " ".join(rationale.split()[:30])  # truncate, don't fail
    return Decision(direction=direction, conviction=conviction, rationale=rationale)


# --------------------------------------------------------------------------- #
# Provider router
# --------------------------------------------------------------------------- #
@dataclass
class AgentResult:
    ok: bool
    decision: Decision | None
    raw_response: str
    input_tokens: int
    output_tokens: int
    error: str | None
    prompt_hash: str


def call_model(model_cfg: dict[str, Any], system: str, user: str,
               temperature: float, seed: int) -> tuple[str, int, int]:
    """Dispatch to the right provider. Returns (raw_text, in_tokens, out_tokens)."""
    import os
    if os.environ.get("PILOT_MOCK") == "1":
        return _mock_call(model_cfg, system, user, seed)
    provider = model_cfg["provider"]
    if provider == "anthropic":
        return _call_anthropic(model_cfg, system, user, temperature, seed)
    if provider == "openai":
        return _call_openai(model_cfg, system, user, temperature, seed)
    if provider in ("google", "gemini"):
        return _call_gemini(model_cfg, system, user, temperature, seed)
    if provider == "xai":
        return _call_xai(model_cfg, system, user, temperature, seed)
    raise ValueError(f"Unknown provider {provider!r}")


def _mock_call(model_cfg, system, user, seed):
    """Offline deterministic stand-in (PILOT_MOCK=1). NO network, NO spend.
    Direction is a deterministic function of (api_model, user prompt) so that
    same-model agents agree more than mixed-model agents — lets you exercise the
    full metrics/stats/storage stack without API keys. NOT real model output."""
    h = int(hashlib.sha256((model_cfg["api_model"] + "|" + user).encode()).hexdigest(), 16)
    # seed-driven perturbation to emulate independent sampling draws
    s = seed if seed is not None else id(object())
    if (h + s * 2654435761) % 100 < 40:
        h = int(hashlib.sha256(f"{h}|{s}".encode()).hexdigest(), 16)
    direction = ["BUY", "HOLD", "SELL"][h % 3]
    conviction = (h % 5) + 1
    raw = json.dumps({"direction": direction, "conviction": conviction,
                      "rationale": "mock deterministic offline response"})
    in_tok = max(1, len((system + user)) // 4)
    out_tok = max(1, len(raw) // 4)
    return raw, in_tok, out_tok


def _call_anthropic(model_cfg, system, user, temperature, seed):
    client = _client("anthropic")
    # Anthropic Messages API does not expose a user-seed param; seed is logged for
    # provenance and used for our own RNG only. Independence is guaranteed by
    # issuing a fresh request per agent (no caching, no shared context).
    resp = client.messages.create(
        model=model_cfg["api_model"],
        max_tokens=int(model_cfg.get("max_tokens", 256)),
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(getattr(b, "text", "") for b in resp.content)
    return text, resp.usage.input_tokens, resp.usage.output_tokens


def _call_openai(model_cfg, system, user, temperature, seed):
    return _openai_compatible_call(_client("openai"), model_cfg, system, user, temperature, seed)


def _openai_compatible_call(client, model_cfg, system, user, temperature, seed):
    """Shared path for OpenAI and xAI (OpenAI-compatible). Resilient to the gpt-5
    reasoning API quirks: uses max_completion_tokens and falls back gracefully if
    the model rejects `temperature` or the older `max_tokens` field."""
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": user}]
    max_out = int(model_cfg.get("max_tokens", 256))
    base = {"model": model_cfg["api_model"], "messages": msgs}
    if seed is not None:            # seed_mode=none -> omit, provider samples freely
        base["seed"] = seed
    if model_cfg.get("reasoning_effort"):
        base["reasoning_effort"] = model_cfg["reasoning_effort"]

    # attempt list: (token_param, include_temperature)
    attempts = [
        ("max_completion_tokens", True),   # modern reasoning models
        ("max_completion_tokens", False),  # model pins temperature=1
        ("max_tokens", True),              # older chat models
    ]
    last_err = None
    for tok_param, with_temp in attempts:
        kwargs = dict(base)
        kwargs[tok_param] = max_out
        if with_temp:
            kwargs["temperature"] = temperature
        try:
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content or ""
            u = resp.usage
            return text, u.prompt_tokens, u.completion_tokens
        except Exception as e:  # try the next signature
            msg = str(e).lower()
            last_err = e
            if any(k in msg for k in ("temperature", "max_tokens", "max_completion",
                                      "unsupported", "unknown parameter", "reasoning_effort")):
                # strip the offending optional param and retry
                if "reasoning_effort" in msg:
                    base.pop("reasoning_effort", None)
                continue
            raise
    raise last_err


def _call_gemini(model_cfg, system, user, temperature, seed):
    key = secretstore.get_key("google")
    max_out = int(model_cfg.get("max_tokens", 512))
    # Prefer the modern google-genai SDK; fall back to legacy google-generativeai.
    try:
        from google.genai import types
        client = _client("gemini")
        gc = {"system_instruction": system, "temperature": temperature,
              "max_output_tokens": max_out,
              "response_mime_type": "application/json"}  # force bare JSON
        # Gemini 3.x flash is a thinking model; hidden reasoning eats the output
        # budget and truncates the JSON. Disable thinking so the answer completes.
        try:
            gc["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        except Exception:
            pass
        if seed is not None:
            gc["seed"] = seed
        resp = client.models.generate_content(
            model=model_cfg["api_model"], contents=user,
            config=types.GenerateContentConfig(**gc))
        text = resp.text or ""
        um = resp.usage_metadata
        return text, um.prompt_token_count, (um.candidates_token_count or 0)
    except ImportError:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_cfg["api_model"], system_instruction=system)
        cfg = {"temperature": temperature, "max_output_tokens": max_out}
        if seed is not None:
            cfg["seed"] = seed
        resp = model.generate_content(user, generation_config=cfg)
        text = resp.text or ""
        um = resp.usage_metadata
        return text, um.prompt_token_count, um.candidates_token_count


def _call_xai(model_cfg, system, user, temperature, seed):
    # xAI Grok is OpenAI-compatible.
    return _openai_compatible_call(_client("xai"), model_cfg, system, user, temperature, seed)


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def run_agent(model_cfg: dict[str, Any], ticker: str, snippet: Snippet,
              temperature: float, seed: int) -> AgentResult:
    user = build_prompt(ticker, snippet)
    ph = prompt_hash(SYSTEM_PROMPT, user)
    try:
        raw, in_tok, out_tok = call_model(model_cfg, SYSTEM_PROMPT, user, temperature, seed)
    except Exception as e:  # network / auth / provider error
        return AgentResult(False, None, "", 0, 0, f"{type(e).__name__}: {e}", ph)
    try:
        dec = parse_strict(raw)
    except Exception as e:
        return AgentResult(False, None, raw, in_tok, out_tok, f"parse: {e}", ph)
    return AgentResult(True, dec, raw, in_tok, out_tok, None, ph)

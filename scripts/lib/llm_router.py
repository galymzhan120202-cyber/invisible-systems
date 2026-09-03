#!/usr/bin/env python3
"""
Multi-provider LLM router with automatic fail-over.

Not "20 keys of one provider" (that violates provider ToS and rarely helps -
limits are org-wide). Instead: an ordered pool of real backends. On a
rate-limit / quota / 5xx the offending key is put on cooldown and the router
moves to the next entry. Cooldown state survives restarts (logs/llm_state.json).

Public API:
    from llm_router import complete, LLMExhausted
    text = complete("author", system="...", user="...", max_tokens=12000)

CLI:
    python llm_router.py --list-models     # list Gemini models visible to your key
    python llm_router.py --smoke           # one tiny call through the 'light' task
"""
from __future__ import annotations
import json, os, sys, time, argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

ROOT = Path(__file__).resolve().parents[2]
POOL_FILE = ROOT / "config" / "llm_pool.yaml"
KEYS_FILE = ROOT / "secrets" / "keys.env"
STATE_FILE = ROOT / "logs" / "llm_state.json"


class LLMExhausted(RuntimeError):
    """Every backend/key for the task is unavailable (cooling or errored)."""


# ----------------------------- config / keys -----------------------------
def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _pool() -> dict:
    _load_env_file(KEYS_FILE)
    return yaml.safe_load(POOL_FILE.read_text(encoding="utf-8"))


def _keys_for(env_name: str) -> list[str]:
    raw = os.environ.get(env_name, "").strip()
    return [k.strip() for k in raw.split(",") if k.strip()]


# ----------------------------- cooldown state -----------------------------
def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(st: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def _cooling(state: dict, tag: str) -> bool:
    return time.time() < state.get("cooldowns", {}).get(tag, 0)


def _cool(state: dict, tag: str, seconds: float) -> None:
    state.setdefault("cooldowns", {})[tag] = time.time() + seconds
    _save_state(state)


# ----------------------------- provider adapters -----------------------------
def _is_rate_limit(exc: Exception) -> tuple[bool, float | None]:
    """Return (is_retryable, retry_after_seconds)."""
    msg = str(exc).lower()
    retry_after = None
    for token in ("retry after ", "retry-after: ", "retrydelay"):
        if token in msg:
            tail = msg.split(token, 1)[1]
            num = "".join(ch for ch in tail[:8] if ch.isdigit())
            if num:
                retry_after = float(num)
            break
    hit = any(s in msg for s in (
        "429", "rate limit", "resource_exhausted", "quota", "overloaded",
        "503", "500", "internal error", "unavailable", "timeout",
        # a dead / renamed / unavailable model is a per-backend problem too:
        # cool it and let the next backend in the task list try.
        "404", "not available", "not found", "no longer available",
        "is not supported", "does not exist",
    ))
    return hit, retry_after


def _call_gemini(model: str, key: str, system: str, user: str,
                 max_tokens: int, temperature: float) -> str:
    import google.generativeai as genai
    genai.configure(api_key=key)
    gm = genai.GenerativeModel(model_name=model, system_instruction=system or None)
    resp = gm.generate_content(
        user,
        generation_config={"max_output_tokens": max_tokens, "temperature": temperature},
    )
    return resp.text


def _call_anthropic(model: str, key: str, system: str, user: str,
                    max_tokens: int, temperature: float) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=model, max_tokens=max_tokens, system=system or anthropic.NOT_GIVEN,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _call_openai_compat(model: str, key: str, base_url: str, system: str, user: str,
                        max_tokens: int, temperature: float) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=base_url)
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": user}]
    r = client.chat.completions.create(
        model=model, messages=msgs, max_tokens=max_tokens, temperature=temperature,
    )
    return r.choices[0].message.content


def _dispatch(be: dict, key: str, system: str, user: str,
              max_tokens: int, temperature: float) -> str:
    p = be["provider"]
    if p == "gemini":
        return _call_gemini(be["model"], key, system, user, max_tokens, temperature)
    if p == "anthropic":
        return _call_anthropic(be["model"], key, system, user, max_tokens, temperature)
    if p == "openai_compat":
        return _call_openai_compat(be["model"], key, be["base_url"], system, user,
                                   max_tokens, temperature)
    raise ValueError(f"unknown provider: {p}")


# ----------------------------- public entry -----------------------------
def complete(task: str, *, system: str = "", user: str,
             max_tokens: int | None = None, temperature: float | None = None,
             verbose: bool = True) -> str:
    pool = _pool()
    order = pool["tasks"].get(task)
    if not order:
        raise ValueError(f"no task '{task}' in {POOL_FILE.name}")
    base_cd = float(pool.get("cooldown_seconds", 90))
    max_tokens = max_tokens or int(pool.get("max_output_tokens", 12000))
    temperature = pool.get("temperature", 0.75) if temperature is None else temperature
    state = _load_state()
    last_err: Exception | None = None
    tried = 0

    for be_name in order:
        be = pool["backends"][be_name]
        keys = _keys_for(be["key_env"])
        if not keys:
            if verbose:
                print(f"  [router] {be_name}: no key in {be['key_env']}, skip")
            continue
        for ki, key in enumerate(keys):
            tag = f"{be_name}#{ki}"
            if _cooling(state, tag):
                if verbose:
                    print(f"  [router] {tag}: cooling, skip")
                continue
            tried += 1
            try:
                if verbose:
                    print(f"  [router] -> {be_name} ({be['model']}) key#{ki}")
                out = _dispatch(be, key, system, user, max_tokens, temperature)
                if not out or not out.strip():
                    raise RuntimeError("empty completion")
                return out
            except Exception as e:  # noqa: BLE001
                last_err = e
                retryable, retry_after = _is_rate_limit(e)
                if retryable:
                    cd = retry_after or base_cd
                    _cool(state, tag, cd)
                    if verbose:
                        print(f"  [router] {tag}: rate/5xx -> cooldown {cd:.0f}s ({e})")
                    continue
                if verbose:
                    print(f"  [router] {tag}: hard error ({e})")
                raise
    raise LLMExhausted(
        f"task '{task}': {tried} attempt(s), all backends unavailable. last: {last_err}"
    )


# ----------------------------- CLI -----------------------------
def _list_models() -> None:
    _load_env_file(KEYS_FILE)
    keys = _keys_for("GEMINI_API_KEYS")
    if not keys:
        sys.exit("no GEMINI_API_KEYS in secrets/keys.env")
    import google.generativeai as genai
    genai.configure(api_key=keys[0])
    for m in genai.list_models():
        if "generateContent" in getattr(m, "supported_generation_methods", []):
            print(f"{m.name:45}  in={m.input_token_limit}  out={m.output_token_limit}")


def _smoke() -> None:
    txt = complete("light", system="You answer in exactly three words.",
                   user="Say hello to the world.", max_tokens=50)
    print("SMOKE OK ->", repr(txt.strip()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.list_models:
        _list_models()
    elif a.smoke:
        _smoke()
    else:
        ap.print_help()

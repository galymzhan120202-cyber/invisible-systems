#!/usr/bin/env python3
"""
10_suggest_topics.py - keep queue/topics.pending.jsonl full.

Asks Gemini (the "light" task) for fresh "Invisible Systems" topics inside the
niche, de-dupes against everything ever queued, and appends the good ones.

    python scripts/10_suggest_topics.py                 # add ~8 new topics
    python scripts/10_suggest_topics.py --count 15
    python scripts/10_suggest_topics.py --min-queue 6   # only if pending < 6 (CI top-up)
    python scripts/10_suggest_topics.py --dry-run       # print, don't write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

QUEUE = ROOT / "queue"
PENDING = QUEUE / "topics.pending.jsonl"
DONE = QUEUE / "topics.done.jsonl"
FAILED = QUEUE / "topics.failed.jsonl"
CONCEPT = ROOT / "CHANNEL-CONCEPT.md"
CHANNEL = ROOT / "config" / "channel.json"

CLUSTERS = [
    "queues-and-waiting", "pricing-and-incentives", "traffic-and-crowds",
    "rules-and-defaults", "platforms-and-algorithms", "platforms-and-layout",
    "institutions-and-bureaucracy", "nature-and-emergent-order",
    "game-theory-in-daily-life",
]
STOP = {"the", "a", "an", "why", "your", "you", "is", "are", "it", "of", "to",
        "in", "on", "and", "for", "at", "always", "more", "than", "up", "how"}


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def toks(*parts: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", " ".join(parts).lower())
    return {w for w in words if w not in STOP and len(w) > 2}


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:60]


# ------------------------------------------------------------------ generation
SYSTEM = """\
You generate new episode topics for the YouTube channel below. Each topic is ONE
everyday "invisible system" - a hidden rule, incentive, feedback loop, queue, or
piece of game theory that shapes ordinary life and that a viewer will recognise.

<channel_concept>
{concept}
</channel_concept>

Hard rules for every topic:
- Explained by MECHANISM, never by statistics or studies. needs_stats is always false.
- Everyday and familiar - the viewer thinks "I've noticed this".
- Showable with a stick figure + abstract shapes (no real brand, place, or face).
- Not a near-duplicate of anything in the avoid list.
- cluster is one of: {clusters}

Return ONE json array in a ```json fence, N objects, nothing else:
[{{"id": "kebab-case-unique-slug",
   "title_working": "Why ... (<= 70 chars, hook-question form)",
   "system": "short phrase naming the actual mechanism",
   "cluster": "<one of the allowed clusters>",
   "needs_stats": false}}]
"""

USER = """\
Give me {n} NEW topics. Avoid anything close to these ({navoid} already used):
{avoid}

Spread them across different clusters. Mechanism-first, no numbers.
"""


def generate(n: int, existing: list[dict], *, attempts: int = 3, verbose: bool = True) -> list[dict]:
    import llm_router

    concept = CONCEPT.read_text(encoding="utf-8") if CONCEPT.exists() else \
        (CHANNEL.read_text(encoding="utf-8") if CHANNEL.exists() else "Invisible Systems channel.")
    avoid = "\n".join(f"- {e.get('title_working', e.get('id',''))}" for e in existing)
    sys_p = SYSTEM.format(concept=concept, clusters=", ".join(sorted(set(CLUSTERS))))
    usr_p = USER.format(n=n + 4, navoid=len(existing), avoid=avoid or "(none yet)")

    seen_tok = [toks(e.get("id", ""), e.get("title_working", ""), e.get("system", ""))
                for e in existing]
    seen_ids = {e.get("id") for e in existing}
    problems = ""
    for i in range(1, attempts + 1):
        raw = llm_router.complete("light", system=sys_p,
                                  user=usr_p + (f"\n\nFix: {problems}" if problems else ""),
                                  max_tokens=4000, temperature=0.9, verbose=verbose)
        m = re.search(r"```json\s*\n(.*?)\n```", raw, re.DOTALL | re.IGNORECASE)
        blob = m.group(1) if m else raw[raw.find("["): raw.rfind("]") + 1]
        try:
            cand = json.loads(blob)
        except json.JSONDecodeError as e:
            problems = f"invalid JSON ({e})"
            if verbose:
                print(f"  [suggest] attempt {i}: {problems}")
            continue

        out: list[dict] = []
        for c in cand:
            if not isinstance(c, dict):
                continue
            tid = slugify(c.get("id") or c.get("title_working", ""))
            title = (c.get("title_working") or "").strip()
            system = (c.get("system") or "").strip()
            cluster = (c.get("cluster") or "").strip().lower()
            if not tid or not title or not system:
                continue
            if c.get("needs_stats"):
                continue
            if tid in seen_ids or any(tid == o["id"] for o in out):
                continue
            t = toks(tid, title, system)
            if any(len(t & s) / max(1, len(t)) > 0.6 for s in seen_tok + [toks(o["id"], o["title_working"]) for o in out]):
                continue
            if cluster not in CLUSTERS:
                cluster = "rules-and-defaults"
            out.append({"id": tid, "title_working": title, "system": system,
                        "cluster": cluster, "needs_stats": False, "status": "pending"})
            seen_ids.add(tid)

        if len(out) >= min(n, 3):
            return out[:n]
        problems = f"only {len(out)} usable after de-dupe; give more, more varied, less like the avoid list"
        if verbose:
            print(f"  [suggest] attempt {i}: {problems}")
    raise RuntimeError(f"topic generation produced too few after {attempts} tries")


# ------------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=8, help="how many to add (default 8)")
    ap.add_argument("--min-queue", type=int, default=0,
                    help="only generate if pending count is below this (CI top-up)")
    ap.add_argument("--dry-run", action="store_true", help="print, do not append")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    pending = read_jsonl(PENDING)
    if args.min_queue and len(pending) >= args.min_queue:
        print(f"queue has {len(pending)} pending (>= {args.min_queue}) - nothing to do")
        return

    existing = pending + read_jsonl(DONE) + read_jsonl(FAILED)
    print(f"{len(existing)} topics known ({len(pending)} pending); asking for {args.count} new")
    fresh = generate(args.count, existing, verbose=not args.quiet)

    for t in fresh:
        print(f"  + [{t['cluster']}] {t['title_working']}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return

    with PENDING.open("a", encoding="utf-8") as fh:
        for t in fresh:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"\nappended {len(fresh)} -> {PENDING.relative_to(ROOT)} "
          f"(pending now {len(pending) + len(fresh)})")


if __name__ == "__main__":
    main()

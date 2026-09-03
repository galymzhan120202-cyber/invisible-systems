#!/usr/bin/env python3
"""
20_produce.py - build ONE Invisible Systems video from a queued topic.

  topic (queue/topics.pending.jsonl)
    -> videos/<date>__<id>/ + brief.json
    -> [LLM author]  storyboard.md, audio/narration.json, audio/sfx-cues.tsv
    -> [LLM author]  animation.html   (validated in headless Chromium, 1 repair try)
    -> produce.ps1   render + TTS + mix + mux + verify
    -> PASS  -> topics.done.jsonl      (status "produced", ready for 30_upload.py)
       FAIL  -> topics.failed.jsonl    (+ reason)

Usage:
    python scripts/20_produce.py                       # next pending topic, full run
    python scripts/20_produce.py --id why-buses-bunch  # a specific pending topic
    python scripts/20_produce.py --dry-run             # author the files, don't render
    python scripts/20_produce.py --slug 2026-09-03__x --no-llm      # re-render existing files
    python scripts/20_produce.py --slug 2026-09-03__x --redo-render # alias of --no-llm

Needs GEMINI_API_KEYS in secrets/keys.env for the author step
(free key: https://aistudio.google.com/apikey). --no-llm skips that.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CONFIG = ROOT / "config"
QUEUE = ROOT / "queue"
VIDEOS = ROOT / "videos"
PENDING = QUEUE / "topics.pending.jsonl"
DONE = QUEUE / "topics.done.jsonl"
FAILED = QUEUE / "topics.failed.jsonl"
PRODUCE_PS1 = ROOT / "scripts" / "produce.ps1"


# ---------------------------------------------------------------- small io
def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def write_jsonl(p: Path, rows: list[dict]) -> None:
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")


def append_jsonl(p: Path, row: dict) -> None:
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- queue moves
def pick_topic(topic_id: str | None) -> tuple[dict, list[dict]]:
    rows = read_jsonl(PENDING)
    if not rows:
        sys.exit("queue/topics.pending.jsonl is empty - add topics first")
    if topic_id:
        for r in rows:
            if r.get("id") == topic_id:
                return r, rows
        sys.exit(f"no pending topic with id '{topic_id}'")
    return rows[0], rows


def drop_from_pending(topic_id: str, rows: list[dict]) -> None:
    write_jsonl(PENDING, [r for r in rows if r.get("id") != topic_id])


# ---------------------------------------------------------------- produce.ps1
def run_produce(slug: str, v: dict) -> int:
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(PRODUCE_PS1), "-Slug", slug,
        "-Fps", str(v["fps"]), "-Width", str(v["width"]), "-Height", str(v["height"]),
        "-Duration", str(v["duration"]), "-Voice", v["voice"],
        "-Workers", str(v.get("render_workers", 4)),
    ]
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def verdict(proj: Path, rc: int) -> tuple[str, str]:
    report = proj / "verification-report.md"
    text = report.read_text(encoding="utf-8") if report.exists() else ""
    if "**PASS**" in text and rc == 0:
        return "PASS", ""
    if "**FAIL**" in text or rc != 0:
        line = next((ln for ln in text.splitlines() if "Errors" in ln or "FAIL" in ln), "")
        return "FAIL", (line.strip() or f"produce.ps1 exit {rc}")
    return "FAIL", "no verification-report.md produced"


# ---------------------------------------------------------------- author step
def author_files(topic: dict, proj: Path, audio: Path, *, verbose: bool) -> dict:
    import os

    import author
    import llm_router

    # keys pre-check so the failure message is useful
    llm_router._load_env_file(llm_router.KEYS_FILE)  # noqa: SLF001
    if not any(k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",")):
        sys.exit("no GEMINI_API_KEYS in secrets/keys.env\n"
                 "  get a free key at https://aistudio.google.com/apikey , then:\n"
                 "  echo GEMINI_API_KEYS=your-key > secrets/keys.env\n"
                 "  (or run with --no-llm to re-render already-authored files)")

    print("== author: storyboard + narration + sfx ==")
    plan = author.author_plan(topic, verbose=verbose)  # retries + validates internally
    (proj / "storyboard.md").write_text(plan["storyboard_md"].strip() + "\n", encoding="utf-8")
    author.write_narration_json(plan["narration"], audio / "narration.json")
    author.write_sfx_tsv(plan["sfx_cues"], audio / "sfx-cues.tsv")
    print(f"  wrote storyboard.md, audio/narration.json ({len(plan['narration'])} scenes),"
          f" audio/sfx-cues.tsv ({len(plan['sfx_cues'])} cues)")

    print("== author: animation.html ==")
    html_path = proj / "animation.html"
    used_fallback = author.build_animation(topic, plan["storyboard_md"],
                                           plan["narration"], html_path, verbose=verbose)
    plan["animation_source"] = "fallback" if used_fallback else "llm"
    return plan


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", help="pending topic id (default: first in the queue)")
    ap.add_argument("--slug", help="existing videos/<slug> folder (with --no-llm)")
    ap.add_argument("--date", help="date prefix for the slug (default: today, UTC)")
    ap.add_argument("--dry-run", action="store_true", help="author the files, skip render")
    ap.add_argument("--no-llm", action="store_true",
                    help="skip the author step; expect storyboard/narration/sfx/animation present")
    ap.add_argument("--redo-render", action="store_true", help="alias of --no-llm")
    ap.add_argument("--keep-going", action="store_true",
                    help="on verify FAIL, exit 0 (for batch runs)")
    ap.add_argument("--notify", action="store_true", help="send a Telegram line at the end")
    ap.add_argument("--quiet", action="store_true", help="less router logging")
    args = ap.parse_args()
    args.no_llm = args.no_llm or args.redo_render
    verbose = not args.quiet

    settings = load_json(CONFIG / "settings.json")
    v = settings["video"]

    # ---- resolve topic + slug ----
    pending_rows: list[dict] = []
    if args.slug:
        proj = VIDEOS / args.slug
        if not proj.is_dir():
            sys.exit(f"no such folder: {proj}")
        slug = args.slug
        brief = load_json(proj / "brief.json") if (proj / "brief.json").exists() else {}
        topic = {"id": brief.get("id", slug.split("__", 1)[-1]),
                 "title_working": brief.get("title_working", slug),
                 "system": brief.get("system", ""), "cluster": brief.get("cluster", "")}
        if not args.no_llm:
            print("note: --slug given without --no-llm; will re-author into the existing folder")
    else:
        topic, pending_rows = pick_topic(args.id)
        date = args.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        slug = f"{date}__{topic['id']}"
        proj = VIDEOS / slug

    audio = proj / "audio"
    audio.mkdir(parents=True, exist_ok=True)

    brief_path = proj / "brief.json"
    brief = {
        "id": topic["id"], "slug": slug,
        "title_working": topic.get("title_working", topic["id"]),
        "system": topic.get("system", ""), "cluster": topic.get("cluster", ""),
        "ratio": v["ratio"], "theme": v["theme"],
        "status": "authoring", "created_at": now_iso(),
        "produced_at": None, "verify": None,
    }
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"topic  : {topic['id']}")
    print(f"slug   : {slug}")
    print(f"folder : {proj}")

    # ---- author ----
    if args.no_llm:
        need = [proj / "animation.html", audio / "narration.json", audio / "sfx-cues.tsv"]
        missing = [str(p.relative_to(ROOT)) for p in need if not p.exists()]
        if missing:
            sys.exit("--no-llm but missing: " + ", ".join(missing))
        print("author : skipped (--no-llm), using existing files")
    else:
        try:
            plan = author_files(topic, proj, audio, verbose=verbose)
            brief["title_working"] = plan.get("title") or brief["title_working"]
            brief["takeaway"] = plan.get("takeaway", "")
            brief["animation_source"] = plan.get("animation_source", "llm")
            brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            brief["status"] = "failed"
            brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
            # infra / config / quota failures are not the topic's fault - leave it
            # pending so a retry picks it up. Only genuine content failures burn it.
            msg = str(e).lower()
            infra = any(s in msg for s in (
                "404", "no longer available", "not available", "not found",
                "api key", "gemini_api_keys", "quota", "exhausted", "rate limit",
                "timeout", "connection", "ssl", "network", "503", "500", "overloaded",
                # repeated LLM formatting flakes: keep the topic, let a human look
                "after 3 attempts", "parseable json", "delimiter"))
            if pending_rows and not infra:
                drop_from_pending(topic["id"], pending_rows)
                append_jsonl(FAILED, {**topic, "status": "failed", "slug": slug,
                                      "failed_at": now_iso(), "reason": f"author: {e}"})
                tail = "moved to topics.failed.jsonl"
            else:
                tail = "left in the queue (looks like an infra/config error - fix and re-run)"
            _notify(args, f"author failed for {slug}: {e}")
            sys.exit(f"AUTHOR FAILED ({tail}): {e}")

    brief["status"] = "rendering"
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.dry_run:
        print("\n--dry-run: authored, not rendered.")
        print("  next:  python scripts/20_produce.py --slug", slug, "--no-llm")
        return

    # ---- produce.ps1 ----
    print("\n== produce.ps1 (render / tts / mix / mux / verify) ==")
    rc = run_produce(slug, v)
    status, reason = verdict(proj, rc)

    brief["status"] = "produced" if status == "PASS" else "failed"
    brief["verify"] = status
    brief["produced_at"] = now_iso()
    brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")

    if pending_rows:
        drop_from_pending(topic["id"], pending_rows)
        if status == "PASS":
            append_jsonl(DONE, {**topic, "status": "done", "slug": slug,
                                "produced_at": dt.date.today().isoformat(),
                                "verify": "PASS", "youtube": None})
        else:
            append_jsonl(FAILED, {**topic, "status": "failed", "slug": slug,
                                  "failed_at": now_iso(), "reason": f"verify: {reason}"})

    art = proj / f"{slug}-WITH-AUDIO.mp4"
    line = (f"produced {slug} - verify {status}"
            + (f" ({reason})" if reason else "")
            + (f"\n{art}" if art.exists() else ""))
    print("\n" + line)
    _notify(args, ("✅ " if status == "PASS" else "⚠️ ") + line)

    if status != "PASS" and not args.keep_going:
        sys.exit(1)
    if status == "PASS":
        print(f"next: python scripts/30_upload.py --slug {slug} --dry-run")


def _notify(args, text: str) -> None:
    if not args.notify:
        return
    try:
        from notify import notify
        notify(text)
    except Exception as e:  # noqa: BLE001
        print(f"  [notify] skipped: {e}")


if __name__ == "__main__":
    main()

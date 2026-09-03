#!/usr/bin/env python3
"""
run_daily.py - one unattended cycle.

    20_produce.py (next pending topic)  ->  if verify PASS  ->  30_upload.py (PRIVATE)

Prints a summary and (with --notify, the default in CI) sends one Telegram line
for the outcome. This is what Windows Task Scheduler or the GitHub Actions cron
calls. The human still approves each video later with 40_review.py.

    python scripts/run_daily.py                 # next pending topic, produce + upload
    python scripts/run_daily.py --id why-buses-bunch
    python scripts/run_daily.py --produce-only  # stop after produce
    python scripts/run_daily.py --no-notify
"""
from __future__ import annotations

import argparse
import os
import re
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

PY = sys.executable or "python"
IN_CI = bool(os.environ.get("CI"))


def _tg(text: str, enabled: bool) -> None:
    if not enabled:
        return
    try:
        from notify import notify
        notify(text)
    except Exception as e:  # noqa: BLE001
        print(f"  [notify] skipped: {e}")


def run(cmd: list[str]) -> tuple[int, str]:
    print("  $", " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.stdout:
        print(p.stdout, end="")
    if p.stderr:
        print(p.stderr, end="", file=sys.stderr)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", help="specific pending topic id")
    ap.add_argument("--produce-only", action="store_true", help="skip the upload step")
    ap.add_argument("--no-notify", action="store_true", help="no Telegram line")
    args = ap.parse_args()
    notify_on = not args.no_notify

    # ---- produce ----
    produce = [PY, "scripts/20_produce.py", "--quiet"]
    if args.id:
        produce += ["--id", args.id]
    rc, out = run(produce)

    if "topics.pending.jsonl is empty" in out:
        print("nothing to do - queue empty")
        _tg("ℹ️ auto-channel: topic queue is empty, nothing produced today.", notify_on)
        return

    m = re.search(r"^slug\s*:\s*(\S+)", out, re.MULTILINE)
    slug = m.group(1) if m else None

    if rc != 0 or "verify PASS" not in out:
        reason = "verify FAIL" if "verify FAIL" in out else f"produce exit {rc}"
        tail = "\n".join(l for l in out.splitlines()[-6:] if l.strip())
        print(f"\nPRODUCE FAILED ({reason})")
        _tg(f"❌ auto-channel produce failed"
            + (f" for {slug}" if slug else "") + f"\n{reason}\n{tail}", notify_on)
        sys.exit(1)

    print(f"\nproduced: {slug}")
    if args.produce_only:
        _tg(f"🎬 auto-channel produced {slug} (verify PASS) - upload skipped (--produce-only)",
            notify_on)
        return

    # ---- upload (PRIVATE) ----
    up = [PY, "scripts/30_upload.py", "--slug", slug]
    if not notify_on:
        up.append("--no-notify")
    rc, out = run(up)
    m = re.search(r"https://youtu\.be/\S+", out)
    url = m.group(0) if m else "(url not parsed)"

    if rc != 0:
        print(f"\nUPLOAD FAILED for {slug}")
        _tg(f"❌ auto-channel: produced {slug} but upload failed (exit {rc})", notify_on)
        sys.exit(2)

    print(f"\nOK: {slug} produced + uploaded PRIVATE -> {url}")
    # 30_upload.py already sent its own Telegram line unless --no-notify
    if not notify_on:
        pass


if __name__ == "__main__":
    main()

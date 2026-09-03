#!/usr/bin/env python3
"""
40_review.py - the human review gate (PLAN section 4).

Every video is uploaded PRIVATE by 30_upload.py. Nothing goes public until a
person watches it here and says so.

    python scripts/40_review.py                      # list every uploaded video + live status
    python scripts/40_review.py --review             # interactive: open each private one, decide
    python scripts/40_review.py --slug <slug> --publish
    python scripts/40_review.py --slug <slug> --schedule "2026-09-10T14:00:00Z"
    python scripts/40_review.py --slug <slug> --keep  # stay private, just annotate reviewedAt

`--schedule` sets privacyStatus=private + publishAt (YouTube publishes it then).
Times are treated as UTC if no offset is given. Needs the `youtube` scope, so the
first run may re-open the browser once to widen the token.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
VIDEOS = ROOT / "videos"
QUEUE = ROOT / "queue"
DONE = QUEUE / "topics.done.jsonl"

from yt_auth import REVIEW_SCOPES, build_service, get_credentials  # noqa: E402


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def parse_when(s: str) -> str:
    t = s.strip().replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        d = dt.datetime.fromisoformat(t)
    except ValueError:
        sys.exit(f"bad --schedule time: {s!r} (try 2026-09-10T14:00:00Z)")
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    if d <= dt.datetime.now(dt.timezone.utc):
        sys.exit(f"--schedule time {d.isoformat()} is not in the future")
    return d.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------- local state
def local_videos() -> list[dict]:
    out = []
    for yt in sorted(VIDEOS.glob("*/youtube.json")):
        d = json.loads(yt.read_text(encoding="utf-8"))
        d["_slug"] = yt.parent.name
        d["_dir"] = yt.parent
        d["_json"] = yt
        out.append(d)
    return out


def video_file(proj: Path, slug: str) -> Path | None:
    for name in (f"{slug}-BILINGUAL-SUBTITLES.mp4", f"{slug}-WITH-AUDIO.mp4",
                 "final-subbed.mp4", "final.mp4", f"{slug}.mp4"):
        if (proj / name).exists():
            return proj / name
    return None


def patch_local(rec: dict, **changes) -> None:
    d = json.loads(rec["_json"].read_text(encoding="utf-8"))
    d.update(changes)
    d["reviewedAt"] = now_iso()
    rec["_json"].write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")


def patch_done_queue(slug: str, **changes) -> None:
    if not DONE.exists():
        return
    rows = [json.loads(ln) for ln in DONE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    hit = False
    for r in rows:
        if r.get("slug") == slug:
            yt = dict(r.get("youtube") or {})
            yt.update(changes)
            yt["reviewedAt"] = now_iso()
            r["youtube"] = yt
            hit = True
    if hit:
        DONE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                        encoding="utf-8")


# ----------------------------------------------------------------- youtube api
def live_status(svc, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        resp = svc.videos().list(part="snippet,status", id=",".join(batch)).execute()
        for it in resp.get("items", []):
            out[it["id"]] = {
                "title": it["snippet"]["title"],
                "privacyStatus": it["status"].get("privacyStatus"),
                "publishAt": it["status"].get("publishAt"),
            }
    return out


def _current_status_body(svc, vid: str) -> dict:
    resp = svc.videos().list(part="status", id=vid).execute()
    items = resp.get("items", [])
    if not items:
        sys.exit(f"video {vid} not found on YouTube (deleted?)")
    return items[0]["status"]


def set_privacy(svc, vid: str, privacy: str, publish_at: str | None = None) -> dict:
    st = _current_status_body(svc, vid)
    st["privacyStatus"] = privacy
    if publish_at:
        st["publishAt"] = publish_at
    else:
        st.pop("publishAt", None)
    body = {"id": vid, "status": st}
    return svc.videos().update(part="status", body=body).execute()


# ----------------------------------------------------------------- actions
def do_publish(svc, rec: dict) -> None:
    set_privacy(svc, rec["videoId"], "public")
    patch_local(rec, privacyStatus="public", publishAt=None)
    patch_done_queue(rec["_slug"], privacyStatus="public")
    print(f"  -> PUBLIC  {rec['url']}")


def do_schedule(svc, rec: dict, when_iso: str) -> None:
    set_privacy(svc, rec["videoId"], "private", publish_at=when_iso)
    patch_local(rec, privacyStatus="private", publishAt=when_iso)
    patch_done_queue(rec["_slug"], privacyStatus="private", publishAt=when_iso)
    print(f"  -> SCHEDULED {when_iso}  {rec['url']}")


def do_keep(rec: dict) -> None:
    patch_local(rec, privacyStatus="private")
    patch_done_queue(rec["_slug"], privacyStatus="private")
    print(f"  -> kept PRIVATE  {rec['url']}")


# ----------------------------------------------------------------- views
def print_table(recs: list[dict], live: dict[str, dict]) -> None:
    if not recs:
        print("no uploaded videos yet (videos/*/youtube.json)")
        return
    print(f"{'slug':<44} {'videoId':<13} {'live':<9} {'publishAt':<21} title")
    print("-" * 110)
    for r in recs:
        lv = live.get(r["videoId"])
        if lv:
            priv, pub, title = lv["privacyStatus"], lv["publishAt"] or "-", lv["title"]
        else:
            priv, pub, title = "GONE?", "-", r.get("title", "")
        print(f"{r['_slug']:<44} {r['videoId']:<13} {priv:<9} {pub:<21} {title[:40]}")


def interactive(svc, recs: list[dict], live: dict[str, dict]) -> None:
    if not sys.stdin or not sys.stdin.isatty():
        sys.exit("--review needs an interactive terminal; use --slug ... --publish/--schedule/--keep")
    pending = [r for r in recs
               if (lv := live.get(r["videoId"])) and lv["privacyStatus"] == "private"
               and not lv["publishAt"]]
    if not pending:
        print("nothing to review - no private, unscheduled videos.")
        return
    print(f"{len(pending)} video(s) to review.\n")
    for r in pending:
        lv = live[r["videoId"]]
        mp4 = video_file(r["_dir"], r["_slug"])
        print(f"── {r['_slug']}")
        print(f"   {lv['title']}")
        print(f"   {r['url']}")
        if mp4:
            print(f"   file: {mp4}")
            try:
                os.startfile(str(mp4))  # noqa: S606  (Windows: opens in default player)
            except Exception:  # noqa: BLE001
                pass
        while True:
            c = input("   [p]ublish now  [s]chedule  [k]eep private  [o]pen again  [q]uit > ").strip().lower()
            if c == "p":
                do_publish(svc, r); break
            if c == "k":
                do_keep(r); break
            if c == "s":
                when = parse_when(input("   publish at (e.g. 2026-09-10T14:00Z): "))
                do_schedule(svc, r, when); break
            if c == "o":
                if mp4:
                    try:
                        os.startfile(str(mp4))
                    except Exception:  # noqa: BLE001
                        pass
                continue
            if c == "q":
                print("stopped."); return
            print("   ? p / s / k / o / q")
        print()


# ----------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", action="store_true", help="interactive walk through private videos")
    ap.add_argument("--slug", help="act on one video")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--publish", action="store_true", help="set public now")
    g.add_argument("--schedule", metavar="WHEN", help="set publishAt (UTC if no offset)")
    g.add_argument("--keep", action="store_true", help="leave private, annotate reviewedAt")
    args = ap.parse_args()

    recs = local_videos()
    creds = get_credentials(scopes=REVIEW_SCOPES)
    svc = build_service(creds)
    live = live_status(svc, [r["videoId"] for r in recs]) if recs else {}

    if args.slug:
        rec = next((r for r in recs if r["_slug"] == args.slug), None)
        if not rec:
            sys.exit(f"no videos/{args.slug}/youtube.json")
        if args.publish:
            do_publish(svc, rec)
        elif args.schedule:
            do_schedule(svc, rec, parse_when(args.schedule))
        elif args.keep:
            do_keep(rec)
        else:
            lv = live.get(rec["videoId"], {})
            print(json.dumps({**{k: rec[k] for k in ("videoId", "url", "title") if k in rec},
                              "live": lv}, indent=2, ensure_ascii=False))
        return

    if args.review:
        interactive(svc, recs, live)
    else:
        print_table(recs, live)


if __name__ == "__main__":
    main()

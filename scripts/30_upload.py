#!/usr/bin/env python3
"""
30_upload.py - upload one finished Invisible Systems video to YouTube as PRIVATE.

The review gate (PLAN section 4): everything lands as `private`; a human opens it
and flips it to `public` / `publishAt` later via 40_review.py.

Auth: OAuth "installed app" flow. First run opens a browser once; the refresh
token is cached in secrets/youtube_token.json and reused after that.

Usage:
    # one-time (or after token loss) - just do the OAuth handshake and show the channel
    python scripts/30_upload.py --auth-only

    # build the metadata and show it, upload nothing
    python scripts/30_upload.py --slug 2026-09-03__why-the-other-lane-looks-faster --dry-run

    # real upload (private)
    python scripts/30_upload.py --slug 2026-09-03__why-the-other-lane-looks-faster
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
CONFIG = ROOT / "config"
VIDEOS = ROOT / "videos"
QUEUE = ROOT / "queue"

from yt_auth import (  # noqa: E402
    RETRIABLE_STATUS, UPLOAD_SCOPES, build_service, get_credentials, show_channel)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- metadata
def find_video_file(proj: Path, slug: str) -> Path:
    for name in (f"{slug}-BILINGUAL-SUBTITLES.mp4", f"{slug}-WITH-AUDIO.mp4",
                 "final-subbed.mp4", "final.mp4", f"{slug}.mp4"):
        p = proj / name
        if p.exists():
            return p
    raise FileNotFoundError(f"no uploadable mp4 in {proj}")


def topic_for_slug(slug: str) -> dict:
    done = QUEUE / "topics.done.jsonl"
    if done.exists():
        for line in done.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("slug") == slug or rec.get("id") == slug:
                return rec
    return {}


def build_body(slug: str, channel: dict, topic: dict, args, proj: Path) -> dict:
    brief = _load_json(proj / "brief.json") if (proj / "brief.json").exists() else {}
    title_working = args.title or brief.get("title_working") or topic.get("title_working") or slug
    takeaway = args.takeaway or brief.get("takeaway") or topic.get("title_working") or title_working
    cluster = brief.get("cluster") or topic.get("cluster", "systems")
    cluster_tag = cluster.replace("-", "")

    title = channel["title_pattern"].format(title=title_working)[:100]
    description = channel["description_template"].format(
        takeaway=takeaway, cluster_tag=cluster_tag)

    tags = list(channel.get("base_tags", []))
    if cluster_tag not in tags:
        tags.append(cluster_tag)

    privacy = args.privacy
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": str(channel.get("category_id", "27")),
            "defaultLanguage": channel.get("language", "en"),
            "defaultAudioLanguage": channel.get("language", "en"),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": bool(channel.get("made_for_kids", False)),
            "madeForKids": bool(channel.get("made_for_kids", False)),
        },
    }


# ------------------------------------------------------------------------ upload
def resumable_upload(request):
    from googleapiclient.errors import HttpError

    response, tries = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"  {int(status.progress() * 100):3d}%")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS:
                tries += 1
                if tries > 6:
                    raise
                back = min(2 ** tries, 60)
                print(f"  {e.resp.status} - retry in {back}s")
                time.sleep(back)
                continue
            raise
    return response


def update_done_queue(slug: str, yt: dict) -> None:
    done = QUEUE / "topics.done.jsonl"
    if not done.exists():
        return
    out = []
    for line in done.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rec = json.loads(s)
        if rec.get("slug") == slug or rec.get("id") == slug:
            rec["youtube"] = yt
        out.append(json.dumps(rec, ensure_ascii=False))
    done.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", help="folder name under videos/")
    ap.add_argument("--auth-only", action="store_true",
                    help="just run the OAuth handshake, save the token, print the channel")
    ap.add_argument("--dry-run", action="store_true", help="print metadata, upload nothing")
    ap.add_argument("--title", help="override title_working")
    ap.add_argument("--takeaway", help="one-sentence takeaway for the description")
    ap.add_argument("--privacy", default=None,
                    help="override privacyStatus (default: settings.review_gate.upload_privacy)")
    ap.add_argument("--no-notify", action="store_true", help="do not send the Telegram message")
    ap.add_argument("--notify-test", action="store_true",
                    help="send a test Telegram message and exit")
    args = ap.parse_args()

    if args.notify_test:
        from notify import notify
        sys.exit(0 if notify("✅ auto-channel Telegram test - it works") else 1)

    settings = _load_json(CONFIG / "settings.json")
    channel = _load_json(CONFIG / "channel.json")
    if args.privacy is None:
        args.privacy = settings.get("review_gate", {}).get("upload_privacy", "private")

    creds = get_credentials(scopes=UPLOAD_SCOPES)
    svc = build_service(creds)

    if args.auth_only:
        print("auth OK")
        show_channel(svc)
        return

    if not args.slug:
        ap.error("--slug is required unless --auth-only")

    proj = VIDEOS / args.slug
    if not proj.is_dir():
        sys.exit(f"no such video folder: {proj}")

    video_file = find_video_file(proj, args.slug)
    topic = topic_for_slug(args.slug)
    body = build_body(args.slug, channel, topic, args, proj)

    print(f"file        : {video_file.name}  ({video_file.stat().st_size / 1e6:.1f} MB)")
    print(f"title       : {body['snippet']['title']}")
    print(f"privacy     : {body['status']['privacyStatus']}")
    print(f"category    : {body['snippet']['categoryId']}")
    print(f"tags        : {', '.join(body['snippet']['tags'])}")
    print("description :")
    for ln in body["snippet"]["description"].splitlines():
        print(f"    {ln}")

    if args.dry_run:
        print("\n--dry-run: nothing uploaded")
        return

    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(video_file), chunksize=8 * 1024 * 1024, resumable=True)
    request = svc.videos().insert(part="snippet,status", body=body, media_body=media)

    print("\nuploading...")
    response = resumable_upload(request)
    vid = response["id"]
    url = f"https://youtu.be/{vid}"
    print(f"done: {url}  ({response['status']['privacyStatus']})")

    yt = {
        "videoId": vid,
        "url": url,
        "privacyStatus": response["status"]["privacyStatus"],
        "title": body["snippet"]["title"],
        "uploadedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    (proj / "youtube.json").write_text(json.dumps(yt, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    update_done_queue(args.slug, yt)
    print(f"wrote {proj / 'youtube.json'} and updated topics.done.jsonl")

    if not args.no_notify:
        try:
            from notify import notify
            notify(
                f"\U0001F4E4 <b>Uploaded</b> — {body['snippet']['title']}\n"
                f"{url}\n"
                f"privacy: <b>{yt['privacyStatus']}</b> · approve it with 40_review.py"
            )
        except Exception as e:  # noqa: BLE001
            print(f"  [notify] skipped: {e}")


if __name__ == "__main__":
    main()

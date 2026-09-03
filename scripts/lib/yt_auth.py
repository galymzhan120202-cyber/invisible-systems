#!/usr/bin/env python3
"""
yt_auth.py - shared YouTube OAuth for 30_upload.py and 40_review.py.

Installed-app flow. First run (or a scope change) opens the browser once; the
refresh token is cached in secrets/youtube_token.json and reused after that.

Scopes:
    youtube.upload  -> videos.insert          (30_upload.py)
    youtube         -> videos.update/list      (40_review.py: flip privacy / schedule)
`youtube` also covers channels.list(mine=True), so no separate readonly scope.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECRETS = ROOT / "secrets"
CLIENT_SECRET = SECRETS / "client_secret.json"
TOKEN_FILE = SECRETS / "youtube_token.json"

# 30_upload.py only inserts videos -> the narrow pair the CI token already has.
UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
# 40_review.py also flips privacy (videos.update) -> needs `youtube`. Superset, so
# one interactive re-auth upgrades the same token for both.
REVIEW_SCOPES = UPLOAD_SCOPES + ["https://www.googleapis.com/auth/youtube"]

RETRIABLE_STATUS = {500, 502, 503, 504}


def get_credentials(*, scopes: list[str] | None = None, interactive: bool | None = None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    scopes = scopes or UPLOAD_SCOPES
    if interactive is None:
        interactive = not os.environ.get("CI")  # GitHub Actions sets CI=true

    if not CLIENT_SECRET.exists():
        sys.exit(f"missing {CLIENT_SECRET} - create a Desktop OAuth client first")

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), scopes)

    if creds and creds.valid and creds.has_scopes(scopes):
        return creds

    if creds and creds.expired and creds.refresh_token and creds.has_scopes(scopes):
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as e:  # noqa: BLE001
            print(f"  token refresh failed ({e}); re-running the consent flow")
            creds = None

    if creds and not creds.has_scopes(scopes):
        print("  saved token is missing a scope this needs; re-authorising once.")

    if not interactive:
        sys.exit("no usable YouTube token (or missing scope) and not interactive.\n"
                 "  run locally once:  python scripts/30_upload.py --auth-only")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), scopes)
    creds = flow.run_local_server(
        port=0, prompt="consent",
        authorization_prompt_message=(
            "\n  A browser window is opening for Google sign-in.\n"
            "  Pick the account that owns the Invisible Systems channel.\n"
            "  \"Google hasn't verified this app\" -> Advanced -> Go to ... (unsafe) -> Allow.\n"))
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"  token saved -> {TOKEN_FILE}")
    return creds


def build_service(creds):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def show_channel(svc) -> None:
    resp = svc.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        print("  (this account has no YouTube channel yet - create one first)")
        return
    ch = items[0]
    sn, st = ch["snippet"], ch.get("statistics", {})
    print(f"  linked channel : {sn['title']}")
    print(f"  channel id     : {ch['id']}")
    print(f"  videos / subs  : {st.get('videoCount', '?')} / {st.get('subscriberCount', '?')}")

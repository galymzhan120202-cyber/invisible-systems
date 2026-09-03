#!/usr/bin/env python3
"""
notify.py - send a short Telegram message (e.g. "video uploaded + link").

Credentials live in  secrets/telegram.json  (git-ignored):

    { "bot_token": "123456:ABC-DEF...", "chat_id": "123456789" }

- bot_token : from @BotFather
- chat_id   : your own numeric id (ask @userinfobot), or a group/channel id

If the file is missing or incomplete, notify() prints a note and returns False
instead of raising - a failed notification must never break the pipeline.

CLI test:
    python scripts/lib/notify.py "hello from auto-channel"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "secrets" / "telegram.json"
API = "https://api.telegram.org/bot{token}/sendMessage"


def _load() -> dict | None:
    if not CONF.exists():
        print(f"  [notify] no {CONF.relative_to(ROOT)} - skipping Telegram message")
        return None
    try:
        d = json.loads(CONF.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  [notify] bad {CONF.name}: {e}")
        return None
    if not d.get("bot_token") or not d.get("chat_id"):
        print(f"  [notify] {CONF.name} needs both 'bot_token' and 'chat_id'")
        return None
    return d


def notify(text: str, *, preview: bool = True, silent: bool = False) -> bool:
    """Send `text` to the configured chat. Returns True on success."""
    conf = _load()
    if conf is None:
        return False
    try:
        import requests

        r = requests.post(
            API.format(token=conf["bot_token"]),
            json={
                "chat_id": str(conf["chat_id"]),
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": not preview,
                "disable_notification": silent,
            },
            timeout=15,
        )
        if r.status_code == 200 and r.json().get("ok"):
            print("  [notify] Telegram message sent")
            return True
        print(f"  [notify] Telegram API said: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  [notify] failed: {e}")
        return False


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) or "test message from auto-channel/notify.py"
    ok = notify(msg)
    sys.exit(0 if ok else 1)

# CI setup — GitHub Actions daily run

The workflow `.github/workflows/daily.yml` produces the next queued topic and
uploads it to YouTube **private** once a day (06:00 UTC) on a `windows-latest`
runner. A human still approves each video with `40_review.py`.

## Cost

$0 at this volume. Private repo = 2,000 free Action-minutes/month; a run is
~4-8 min. If that ceiling is ever hit, make the repo **public** (unlimited free
minutes) — the repo holds no secrets (all four are GitHub Actions Secrets).

## Required GitHub Actions secrets

Repo → Settings → Secrets and variables → Actions:

| Secret | Value | Source |
|---|---|---|
| `CLIENT_SECRET_JSON` | full contents of `secrets/client_secret.json` | Google Cloud OAuth client (Desktop) |
| `YOUTUBE_TOKEN_JSON` | full contents of `secrets/youtube_token.json` | created by `python scripts/30_upload.py --auth-only` |
| `TELEGRAM_JSON` | full contents of `secrets/telegram.json` | `{"bot_token": "...", "chat_id": "..."}` |
| `GEMINI_API_KEYS` | the value only (comma-separated), no `GEMINI_API_KEYS=` prefix | https://aistudio.google.com/apikey |

Set them from the local files with `gh`:

```sh
gh secret set CLIENT_SECRET_JSON  < secrets/client_secret.json
gh secret set YOUTUBE_TOKEN_JSON  < secrets/youtube_token.json
gh secret set TELEGRAM_JSON       < secrets/telegram.json
gh secret set GEMINI_API_KEYS --body "$(sed 's/^GEMINI_API_KEYS=//' secrets/keys.env)"
```

## Run it

- Automatic: daily at 06:00 UTC (GitHub cron is best-effort, can lag; the
  self-commit in the workflow keeps the schedule from being disabled for
  inactivity).
- Manual: Actions tab → **daily** → *Run workflow* (optional `topic_id`,
  `count`, `produce_only`).

### Videos per day

Repo → Settings → Secrets and variables → Actions → **Variables** →
`DAILY_COUNT` (default 1). Each cron run then produces + uploads that many.

### Public vs private (review gate)

`DAILY_PRIVACY` repo variable — **leave it unset** and every video uploads
`private`; you then watch each one and publish with `40_review.py`. Set it to
`public` only after ~20 human-reviewed videos have gone out and the animation
quality is proven.

> Why the gate matters: a brand-new channel auto-publishing several
> LLM-generated videos a day is the exact pattern YouTube's spam systems flag
> (`PLAN.md` §6.6, `CHANNEL-CONCEPT.md` §7). Getting this wrong can cost the
> whole channel. `private` uploads carry none of that risk.

Practical ceilings: YouTube upload quota ~6/day; a run is ~8 min → 16 billed
Action-minutes, so 3/day ≈ 1,440 min/month against the 2,000 free (private repo)
— go public for headroom. And every video is private and needs a human in
`40_review.py`, so more/day = more review time. New-channel + auto-content policy
risk argues for **1/day** until the channel has a track record.

## What the workflow does

1. checkout, Python 3.13, `pip install -r requirements.txt`, `playwright install chromium`, ensure ffmpeg
2. write the four secrets back into `secrets/`
3. `python scripts/run_daily.py` → `20_produce.py` (next topic) → if verify PASS → `30_upload.py` (private)
4. commit the mutated `queue/*.jsonl` + new `videos/<slug>/` sources back (`[skip ci]`, GITHUB_TOKEN pushes don't retrigger)
5. upload the MP4 as a 14-day build artifact
6. Telegram line on success (from `30_upload.py`) or failure (from `run_daily.py` / a final infra-failure step)

## Token note

`youtube_token.json` holds a refresh token. The OAuth app is "in production", so
it does not expire on a schedule. If Google ever rotates it, the run fails and
you get a Telegram alert — re-run `30_upload.py --auth-only` locally and update
the `YOUTUBE_TOKEN_JSON` secret.

The token committed here has scopes `youtube.upload` + `youtube.readonly` (enough
for CI, which only inserts). `40_review.py` needs the wider `youtube` scope and
triggers a one-time browser re-auth locally — that is a human step and never runs
in CI.

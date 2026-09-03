#!/usr/bin/env python3
"""
author.py - the AI "director" step of the pipeline.

Two calls to the LLM router (task = "author"):

    1. author_plan(topic, cfg)      -> storyboard.md text + narration[] + sfx_cues[]
    2. author_animation(topic, ...) -> a single deterministic animation.html string

Plus:

    validate_narration(...)   -> list[str] of problems
    validate_sfx(...)         -> list[str]
    validate_animation(path)  -> list[str]   (loads it in headless Chromium)

Nothing here writes files or touches the queue - 20_produce.py does that.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import llm_router

ROOT = Path(__file__).resolve().parents[2]
CONCEPT = ROOT / "CHANNEL-CONCEPT.md"
REFERENCE_HTML = (ROOT / "videos" / "2026-09-03__why-the-other-lane-looks-faster"
                  / "animation.html")

# the eight files under assets/audio/sfx (no path, just names)
SFX_ASSETS = [
    "click-soft.mp3", "complete-done.mp3", "drop-thud.mp3", "focus.mp3",
    "stack-collapse.mp3", "transform.mp3", "whoosh-fast.mp3", "whoosh.mp3",
]

SCENES = 6
SCENE_SECONDS = 10.0


# --------------------------------------------------------------------- helpers
def _strip_fences(text: str, langs=("json", "html", "")) -> str:
    t = text.strip()
    m = re.match(r"^```[a-zA-Z]*\s*\n(.*)\n```$", t, re.DOTALL)
    if m:
        return m.group(1).strip()
    # tolerate a leading ```lang with no matching close
    for lang in langs:
        pre = f"```{lang}"
        if t.startswith(pre):
            t = t[len(pre):].lstrip("\n")
    if t.endswith("```"):
        t = t[:-3].rstrip()
    return t.strip()


def _first_fence(text: str, lang: str) -> str | None:
    m = re.search(rf"```{lang}[^\n]*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_storyboard(text: str) -> str:
    """The storyboard is the ```markdown fence, or just everything after the JSON."""
    sb = _first_fence(text, "markdown") or _first_fence(text, "md")
    if sb:
        return sb.strip()
    m = re.search(r"```(?:json)?\s*\n.*?\n```(.*)$", text, re.DOTALL | re.IGNORECASE)
    tail = (m.group(1) if m else text).strip()
    tail = _strip_fences(tail, langs=("markdown", "md", ""))
    # drop a leading "Block 2" / "Storyboard:" label line if present
    tail = re.sub(r"^\s*(block\s*2[:.]?|storyboard[:.]?)\s*\n", "", tail,
                  flags=re.IGNORECASE)
    return tail.strip()


def _extract_json(text: str) -> dict:
    # prefer an explicit ```json fence; fall back to a bare {...} span
    cand = _first_fence(text, "json")
    if cand is None:
        cand = _strip_fences(text)
    try:
        return json.loads(cand)
    except json.JSONDecodeError:
        a, b = cand.find("{"), cand.rfind("}")
        if a != -1 and b > a:
            return json.loads(cand[a:b + 1])
    raise ValueError("response had no parseable JSON object")


def _concept() -> str:
    for p in (CONCEPT, ROOT.parent / "CHANNEL-CONCEPT.md"):
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def _reference_html() -> str:
    return REFERENCE_HTML.read_text(encoding="utf-8") if REFERENCE_HTML.exists() else ""


# ------------------------------------------------------------------- call 1
PLAN_SYSTEM = """\
You are the director of "Invisible Systems", a channel of 60-second stick-figure
explainers about hidden everyday systems. You write the production plan for ONE
video. Follow the channel concept below.

<channel_concept>
{concept}
</channel_concept>

Rules:
- Vertical 9:16, dark theme (black canvas, white line art).
- Exactly 6 scenes, ~10 s each, ~60 s total.
- English voiceover, 130-150 words total, natural spoken American English,
  bright energetic adult-female narrator. 18-25 words per scene, whole sentences.
- Narrative arc: use the Harmon Story Circle (YOU/NEED -> GO -> SEARCH -> FIND ->
  TAKE -> RETURN/CHANGE) as the DEFAULT when the topic fits it; otherwise use
  Educational (surprising hook -> setup -> mechanism -> consequence -> practical
  meaning -> takeaway). Do not force a bad fit.
- No on-screen text anywhere. A clock is an icon (circle + hands), never digits;
  a card/sign is an icon, never words. Colour semantics: signal blue = the
  system/rule revealed; warm amber = YOU / what you want; coral red = the naive
  wrong model. Max 3 accents.
- One or two hero elements that persist and transform across all 6 scenes.
- No invented statistics, studies, or quotes. Pure mechanism.
- SFX only from this exact set (filenames): {sfx}. Use ~2-3 per scene, on
  decisions / focus shifts / transforms / impacts / completion - not every motion.

Output TWO blocks and nothing else.

Block 1 - a ```json fence with EXACTLY this shape (no other keys, no comments,
valid JSON, all strings one line):
{{
  "title": "<= 70 chars, working title, no channel suffix",
  "system": "one phrase naming the mechanism",
  "cluster_tag": "one lowercase word",
  "takeaway": "one plain sentence stating what the viewer now understands (goes first in the YouTube description; not a repeat of the title)",
  "narration": [
     {{"id": "scene-01", "text": "<exact VO, one line>", "rate": "+5%", "start": 0.3}},
     ... exactly 6, ids scene-01..scene-06, start strictly increasing,
     near n*10+0.3, last start <= 54, 130-150 words TOTAL across all six ...
  ],
  "sfx_cues": [
     {{"time": 0.6, "asset": "focus.mp3", "gain": 0.26}}, ...
     ~2-3 per scene, times in [0,60) strictly increasing, gain 0.20-0.32 ...
  ]
}}

Block 2 - the storyboard as Markdown, placed AFTER the json block (a ```markdown
fence is fine but not required): a title line, bullets for system / narrator /
palette / hero element, then a 6-row table with columns
`# | Time | Story beat | Stick-figure scene | Motion / camera / transition |
English VO | SFX`, then a short "Continuity map" naming what each scene boundary
shares. Concrete geometry, not vague adjectives.
"""

PLAN_USER = """\
Topic id: {id}
Working title: {title_working}
System / mechanism: {system}
Cluster: {cluster}

Write the plan now. Remember: mechanism only, no numbers, 130-150 VO words total,
6 scenes, hero element that morphs scene to scene, SFX only from the allowed set.
"""


def author_plan(topic: dict, *, attempts: int = 3, verbose: bool = True) -> dict:
    system = PLAN_SYSTEM.format(concept=_concept(), sfx=", ".join(SFX_ASSETS))
    base_user = PLAN_USER.format(
        id=topic.get("id", "?"),
        title_working=topic.get("title_working", topic.get("id", "?")),
        system=topic.get("system", ""),
        cluster=topic.get("cluster", ""),
    )
    problems = ""
    last_err = "unknown"
    for i in range(1, attempts + 1):
        user = base_user + (
            f"\n\nAttempt {i}. Your previous response was rejected:\n{problems}\n"
            "Resend BOTH blocks in the exact required format, fixing this."
            if problems else "")
        try:
            raw = llm_router.complete("author", system=system, user=user,
                                      max_tokens=8000, temperature=0.8, verbose=verbose)
            data = _extract_json(raw)
            data["storyboard_md"] = _extract_storyboard(raw)
            for key in ("title", "narration", "sfx_cues"):
                if key not in data:
                    raise ValueError(f"missing '{key}'")
            data.setdefault("takeaway", data["title"])
            if len(data["storyboard_md"]) < 120:
                raise ValueError("storyboard text missing or too short")
            errs = validate_narration(data["narration"]) + validate_sfx(data["sfx_cues"])
            if errs:
                raise ValueError("; ".join(errs))
            return data
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            problems = last_err
            if verbose:
                print(f"  [author_plan] attempt {i} rejected: {last_err}")
    raise RuntimeError(f"author_plan failed after {attempts} attempts: {last_err}")


# ------------------------------------------------------------------- call 2
ANIM_SYSTEM = """\
You write ONE self-contained HTML file: a deterministic, seekable SVG animation
for a 60-second 1080x1920 dark-theme stick-figure explainer.

HARD CONTRACT - the renderer drives it frame by frame:
- Pure inline <script>, no external resources, no network, no <img>.
- Expose exactly:
      window.__duration = 60;
      window.__seek = function (seconds) {{ render(seconds); }};
  and set  window.__ready = true  only AFTER calling render(0) once.
- When  window.__recording === true  do NOT start any requestAnimationFrame loop
  and do NOT loop playback. (Keep a rAF fallback for  !window.__recording  so it
  previews in a browser.)
- render(t) MUST be a pure function of t: derive scene index and local time from
  t, rebuild #stage.innerHTML from scratch every call, never depend on previous
  frames, seed any randomness from an index (a sin-hash like the reference).
  Frames are requested OUT OF ORDER and in parallel - every t must be correct on
  its own.
- 6 scenes of 10 s. Canvas 1080x1920, keep action inside the top/bottom ~8%.
- One or two hero elements persist across all 6 scenes and visibly morph at each
  boundary (line -> belt -> column -> finish line ...). No full-frame slide cuts.
- Frame 0 is a complete composition. The final frame is stable >= 0.8 s. Never
  fade to black.
- ABSOLUTELY NO TEXT. Never emit an SVG <text> element or canvas fillText, not
  even for a clock or a sign. A clock is a circle with two hands. A sign is a
  rectangle with a simple glyph (arrow, dot, bar). Never render digits or letters.
- Colours: white #FFFFFF line art on #000000; accents signal blue #4C86F0,
  warm amber #F2A93B, coral red #FF5B5B, muted grey #8A93A6. Max 3 accents live.

Below is a COMPLETE working reference for a *different* topic. Match its
structure, helper style, quality and the contract exactly. Do NOT copy its
content - build the new topic's scenes.

<reference_animation_html>
{reference}
</reference_animation_html>

Output ONLY the HTML file - start with <!doctype html>, end with </html>. No
Markdown fences, no explanation.
"""

ANIM_USER = """\
Build animation.html for this video.

<storyboard>
{storyboard}
</storyboard>

Narration timing (scene -> start second), for syncing motion beats:
{timing}

Deliver the full HTML now.
"""


def author_animation(topic: dict, storyboard_md: str, narration: list[dict],
                     *, repair_error: str | None = None, verbose: bool = True) -> str:
    system = ANIM_SYSTEM.format(reference=_reference_html())
    timing = "\n".join(f"  {n['id']}: {n['start']}s" for n in narration)
    user = ANIM_USER.format(storyboard=storyboard_md, timing=timing)
    if repair_error:
        user += (
            "\n\nYour previous attempt FAILED validation with:\n"
            f"{repair_error}\n"
            "Return a corrected full HTML file that fixes exactly this.\n"
        )
    raw = llm_router.complete("author", system=system, user=user,
                              max_tokens=20000, temperature=0.5, verbose=verbose)
    html = _strip_fences(raw, langs=("html", ""))
    if "<!doctype" not in html.lower():
        i = html.lower().find("<!doctype")
        if i > 0:
            html = html[i:]
    return html


# ----------------------------------------------------------------- validators
def validate_narration(narration: list[dict]) -> list[str]:
    errs: list[str] = []
    if len(narration) != SCENES:
        errs.append(f"narration has {len(narration)} entries, need {SCENES}")
    last = -1.0
    words = 0
    for i, n in enumerate(narration, 1):
        if not n.get("text", "").strip():
            errs.append(f"scene {i}: empty text")
        words += len(re.findall(r"[A-Za-z']+", n.get("text", "")))
        try:
            start = float(n["start"])
        except (KeyError, TypeError, ValueError):
            errs.append(f"scene {i}: bad start")
            continue
        if start < 0 or start >= 60:
            errs.append(f"scene {i}: start {start} out of [0,60)")
        if start <= last:
            errs.append(f"scene {i}: start {start} not after previous {last}")
        last = start
    if not (110 <= words <= 165):
        errs.append(f"VO word count {words} outside 110-165 (target 130-150)")
    return errs


def validate_sfx(sfx_cues: list[dict]) -> list[str]:
    errs: list[str] = []
    if not sfx_cues:
        errs.append("no sfx cues")
    last = -1.0
    for i, c in enumerate(sfx_cues, 1):
        asset = c.get("asset")
        if asset not in SFX_ASSETS:
            errs.append(f"cue {i}: asset '{asset}' not in allowed set")
        try:
            t = float(c["time"])
        except (KeyError, TypeError, ValueError):
            errs.append(f"cue {i}: bad time")
            continue
        if t < 0 or t >= 60:
            errs.append(f"cue {i}: time {t} out of [0,60)")
        if t < last:
            errs.append(f"cue {i}: time {t} before previous {last}")
        last = t
        try:
            g = float(c.get("gain", 0))
            if not (0.1 <= g <= 0.4):
                errs.append(f"cue {i}: gain {g} outside 0.10-0.40")
        except (TypeError, ValueError):
            errs.append(f"cue {i}: bad gain")
    return errs


def validate_animation(html_path: Path, duration: float = 60.0) -> list[str]:
    """Load the file in headless Chromium and exercise the seek contract."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ["playwright not installed - cannot validate animation.html"]

    errs: list[str] = []
    src = html_path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"<text[\s>]", src) or "fillText" in src or ".textContent" in src:
        errs.append("contains on-screen text (<text>/fillText) - channel rule is NO text; "
                    "use icons only (a clock = circle + hands, never digits)")
    probes = [0.0, duration * 0.17, duration * 0.5, duration * 0.83,
              max(0.0, duration - 0.2)]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_context(
                viewport={"width": 1080, "height": 1920}, device_scale_factor=1
            ).new_page()
            page.add_init_script("window.__recording = true; window.__seekRender = true;")
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=30_000)
            try:
                page.wait_for_function(
                    "window.__ready === true && typeof window.__seek === 'function'",
                    timeout=10_000,
                )
            except Exception:  # noqa: BLE001
                browser.close()
                return ["window.__ready never became true / window.__seek missing "
                        "within 10 s"]

            dur = page.evaluate("window.__duration")
            if not isinstance(dur, (int, float)) or abs(dur - duration) > 0.5:
                errs.append(f"window.__duration = {dur!r}, expected ~{duration}")

            seen = {}
            for t in probes:
                html = page.evaluate(
                    "t => { window.__seek(t); "
                    "const s = document.getElementById('stage'); "
                    "return s ? s.innerHTML : null; }", t)
                if html is None:
                    errs.append("no #stage element after __seek")
                    break
                if len(html.strip()) < 40:
                    errs.append(f"#stage nearly empty at t={t:.1f}s "
                                f"({len(html.strip())} chars)")
                seen[t] = html
            if len(seen) >= 2 and len(set(seen.values())) == 1:
                errs.append("#stage identical at every probed time - not animating")
            browser.close()
    except Exception as e:  # noqa: BLE001
        errs.append(f"animation validation crashed: {e}")
    return errs


# --------------------------------------------------------------------- writers
def write_sfx_tsv(sfx_cues: list[dict], path: Path) -> None:
    lines = ["time\tasset\tgain"]
    for c in sfx_cues:
        lines.append(f"{float(c['time']):.2f}\t{c['asset']}\t{float(c['gain']):.2f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_narration_json(narration: list[dict], path: Path) -> None:
    clean = [
        {"id": n.get("id", f"scene-{i:02d}"),
         "text": n["text"].strip(),
         "rate": n.get("rate", "+5%"),
         "start": round(float(n["start"]), 2)}
        for i, n in enumerate(narration, 1)
    ]
    path.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")

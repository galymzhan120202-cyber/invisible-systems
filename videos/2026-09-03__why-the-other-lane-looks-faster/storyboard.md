# Storyboard — Why the other lane always looks faster

- **Channel:** Invisible Systems
- **System:** traffic flow / selection bias in perceived motion (Redelmeier–Tibshirani effect)
- **Ratio / theme:** 9:16 (1080×1920) · dark (black canvas, white line art)
- **Narrator:** bright, energetic adult female, natural American English (`en-US-AvaNeural`)
- **Structure:** Harmon Story Circle, 8 beats compressed into 6 scenes.
- **Accent palette (semantic):**
  - **signal blue** — the system revealed in FIND: lanes, belts, the wave
  - **warm amber** — YOU / NEED: your car, your progress, what you want
  - **coral red** — the naive model in SEARCH: the "faster" other lane, the false signal
- **Hero element (survives all 6 scenes):** two parallel lane lines.
  lines → bent funnel → two conveyor belts → speed-swapped belts → belts shedding a memory trail → one shared finish line → back to two plain lines (callback).
- **On-screen text:** none. Cards / meters / counters are icon-only. Optional overlay phrases live in §Overlays, never in the animation.

## Narration (VO) — 141 words, ~58 s

| # | Time | Story Circle | English VO (exact) | Stick-figure scene | Motion / camera / transition | SFX |
|---|---|---|---|---|---|---|
| 1 | 0–10s | **1 YOU + 2 NEED** | "You're in ordinary traffic, just moving with everyone else. And you want one simple thing: to get ahead. A small, reasonable urge." | A sits in an amber car on the left of two white lane lines, rolling gently forward with a few idle white dots in the right lane. A soft amber arrow pulses ahead of the car. | Slow push-in. Lane lines draw top-to-bottom. Amber "want" arrow pulses twice. End: calm two-lane frame, car left. | `focus` @0.6, `click-soft` @6.4 (arrow pulse) |
| 2 | 10–20s | **3 GO** | "So you take the lane that's rolling. And seconds later, the lane you just left surges past you. You feel it in your chest — and you notice it always happens." | Right lane's dots slide forward; A hops the amber car right; immediately the left lane's dots surge ahead past A. A's head turns back toward the left lane. | Match-cut on the amber car for the lane hop. Left-lane surge = fast lateral streak. Camera nudges with the hop. End: car right, left lane ahead. | `whoosh-fast` @11.4 (lane change), `whoosh` @14.6 (left surge), `drop-thud` @17.8 |
| 3 | 20–30s | **4 SEARCH** | "So you go looking for the trick. Is something out there watching you, picking whichever lane you leave? It isn't. Traffic just moves in waves." | The two lanes bend inward into a funnel pointed at A; a coral spotlight snaps onto whichever lane A is NOT in, jumping back and forth; then the funnel straightens and the coral light dissolves. | Lanes warp toward centre (shared geometry). Spotlight jumps lane-to-lane 3×. Camera tilts, then levels as lanes straighten. End: two straight lines, no coral. | `transform` @20.4 (funnel), `focus` @23.0 (spotlight jump), `focus` @25.5 (jump) |
| 4 | 30–40s | **5 FIND** | "Then it clicks. When your lane crawls, cars pour past you for minutes. When your lane flies, you overtake them in seconds. You spend more time being passed than passing." | Straight lines thicken into two blue conveyor belts. First: A's belt crawls while the other floods with white dots streaming past, each trailing a short coral streak. Then belts swap: A's belt surges, sparse dots flick past once and vanish. A small amber "time" bar along the bottom-safe zone fills only while A is being passed. | Lines morph to belts (continuity). Long lateral hold on the flood, then a hard speed-swap snap and quick overtake wipes. Amber bar fills icon-only, no numbers. | `transform` @30.4 (belt morph), `whoosh` @32.6, `whoosh-fast` @36.4 (swap), `stack-collapse` @38.6 (bar tick) |
| 5 | 40–50s | **6 TAKE** | "And that's the price. Every losing moment gets stored. Your memory of the whole drive fills up with the other lane winning — a feeling that's hard to shake." | The coral streaks left on the passing dots peel off and stack into a tall coral memory column beside A; A's own amber column of gains stays short. A stands beside the two columns, dwarfed by the coral one. | Streaks lift and stack (match-motion from scene 4). Camera pulls back to reveal tall coral vs short amber. Slight hold on A looking up at the coral column. | `focus` @41.0, `stack-collapse` @44.0, `drop-thud` @48.4 |
| 6 | 50–60s | **7 RETURN + 8 CHANGE** | "Tomorrow you're back in the same traffic, and both lanes still arrive together. But now you can see the wave — and the other lane stops fooling you." | Camera pulls fully back: both blue belts curve into a single white finish line; A's amber car and a rival white dot reach it at the exact same instant. The belts snap back into the two plain lane lines from the opening; the amber "want" arrow reappears, calm. | Belts converge → one finish line → simultaneous arrival. Final morph back to two lines. Hold final frame ≥0.9 s. No fade to black. | `complete-done` @52.4 (arrival), `focus` @57.2 (arrow returns) |

## Continuity map (scene boundaries)

- 1→2: calm two straight lane lines → same lines, dots begin to move and the car hops.
- 2→3: same lines bend inward into a funnel.
- 3→4: funnel straightens → the straight lines thicken into two belts.
- 4→5: the coral streaks already on the passing dots lift off and stack.
- 5→6: pull back; belts curve into one finish line, then collapse to the two opening lines + amber arrow.

## Overlays (post-production only — NOT in the animation)

- Clip 2, top safe area: "YOU SWITCH…" → optional.
- Clip 6, centre: "IT'S JUST A WAVE." → optional.

## First / final frame

- Frame 0: complete composition — two full lane lines, amber car parked left, amber arrow ahead of it, three idle dots in the right lane. Nothing mid-transition.
- Final frame: two plain lane lines, amber car and rival dot together on one white finish line, amber arrow ahead, centred and stable.

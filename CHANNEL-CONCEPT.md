# Channel Concept — Invisible Systems

> Осы құжат `20_produce.py` ішіндегі AI агентке де, `10_suggest_topics.py` топик
> генераторына да кіріс болады. Қозғалтқыш контракттарымен үйлеседі:
> `stickman-video-director-upgraded-share-/skill/directing-stickman-videos-end-to-end/`.

---

## 1. Позиция

**Invisible Systems** — 60 секундта күнделікті өмірдегі бір "көрінбейтін жүйені"
түсіндіретін сызық-адам анимациясы: жасырын ережелер, ынталар (incentives), кері
байланыс циклдары, кезектер, game theory, механизм дизайны.

**Бір сөйлеммен:** "Неге әлем дәл осылай құрылған — және оны байқамайсың."

**Аудитория:** 18–34, техника/ғылымға бейім, "how the world works" қызығушылығы
(CGP Grey, Veritasium, Wendover, Primer көретіндер). Ағылшын тілді, жаһандық.

**Неге бұл ниша:** қозғалтқышқа тамаша сай (кіріктірілген мысал видео дәл осы
форматта — "лифт неге кезекпен жүрмейді"), бәсеке психология/қаржыдан жұқа,
контент мәңгілік — артқы каталог жылдар бойы көрсетіледі.

---

## 2. Канал атаулары (handle бос болмаса, реті бойынша)

1. **Invisible Systems** — `@InvisibleSystems` / `@invisible.systems`
2. **The Hidden Rules** — `@TheHiddenRules`
3. **Unseen Machinery** — `@UnseenMachinery`
4. **Second-Order** — `@SecondOrderYT` (game theory реңкі)

**Канал сипаттамасы (About):**
> Every day you move through systems you never see — queues, incentives, feedback
> loops, quiet rules that decide how things actually work. One 60-second stick-figure
> explainer at a time, Invisible Systems makes them visible. New short every [X].

---

## 3. Визуал бірегейлік (қозғалтқыш параметрлері)

| Параметр | Мән |
|---|---|
| Пропорция | **9:16** (1080×1920) — Shorts / TikTok / Reels |
| Тема | **dark** (қара кенеп, ақ сызық-адам) — мобильде премиум, техно реңк |
| Ұзақтық | ~60 сек, VO 130–150 ағылшын сөзі, 6 сахна |
| Акцент палитрасы (макс. 3, тек қарапайым атаумен) | **signal blue** = жүйе / ереже / құрылым · **warm amber** = ынта / адам нені қалайды · **coral red** = үйкеліс / сәтсіздік / аңғал тәсіл |
| Экранда мәтін | **ЖОҚ** (контракт талабы). Хабарлама/карта/сағат — тек белгіше. Қосымша overlay сөздер тек кейінгі өңдеуде, генерация промптына кірмейді |
| Интро/аутро | Әркелкі — "жаппай өндіріс" таңбасын болдырмау үшін бірінші сахна hook-ы мен соңғы кадр callback-і әр видеода өзгеше |

**Thumbnail (Shorts үшін міндетті емес, бірақ пайдалы):** қара фон, ақ сызық-адам
бір объектімен, 1 акцент түс, 2–4 сөздік сұрақ (мыс. "WHY THE OTHER LANE?").
Thumbnail мәтіні — генерация видеосынан бөлек, кейінгі өңдеуде.

---

## 4. Эпизод формуласы — Harmon Story Circle (әр видео осы құрылымда)

Дэн Хармонның 8 қадамы 6 сахнаға сығылады (`storyboard-template.md` талабына сай).
"YOU" = көрермен: ол таныс жағдайдағы кейіпкер. Жүйе — оны өзгертетін "әлем".

| Сахна | Уақыт | Story Circle қадам(дары) | Мақсаты |
|---|---|---|---|
| 1 | 0–10s | **1 YOU + 2 NEED** | Көрерменді таныс жағдайда орнату + ол нені қалайды (мыс. "жылдам жүру") |
| 2 | 10–20s | **3 GO** | Табалдырықтан аттау — таныс емес жағдайға түсу ("неге бұлай болып жатыр?") |
| 3 | 20–30s | **4 SEARCH** | Бейімделу, себебін іздеу — аңғал болжам сынға түседі (coral red) |
| 4 | 30–40s | **5 FIND** | Іздегенін табу — нақты механизм ашылады (signal blue) |
| 5 | 40–50s | **6 TAKE** | Баға төлеу — иллюзияның бұзылуы, "мені жылдар бойы алдап келген" салдары |
| 6 | 50–60s | **7 RETURN + 8 CHANGE** | Сол жолға қайта оралу, бірақ өзгерген — callback, "енді көресің" |

**Түс семантикасы Story Circle-мен:** coral red — SEARCH сатысындағы аңғал/жалған
модель; signal blue — FIND сатысында ашылатын жүйе; warm amber — YOU/NEED
(көрермен нені қалайды, оның "жеңісі").

Наратив тоны: **curiosity → tension → click → cost → clarity**.

Наратор (әдепкі): жарқын, энергиялы ересек әйел дауысы, табиғи американдық
ағылшын (Edge TTS: `en-US-AvaNeural` немесе `en-US-JennyNeural`).

**Дереккөз адалдығы:** нақты статистика/зерттеу/дәйексөз ойлап таппау. Тақырып
таза механизмге құрылады — сан керек болса, тақырыпты өзгерту.

---

## 5. Топик генераторы спецификациясы (`10_suggest_topics.py`)

**Тапсырма:** ниша ішінде N жаңа тақырып ұсыну. Әрқайсысы —
`topics.pending.jsonl`-ге бір жол:

```json
{"id": "why-the-other-lane-looks-faster",
 "title_working": "Why the other lane always looks faster",
 "system": "traffic flow / selection bias in perceived motion",
 "circle": {
   "you":    "You're in ordinary traffic, moving with the flow.",
   "need":   "You just want to get ahead — a small, reasonable urge.",
   "go":     "You switch lanes; then the lane you left surges past you.",
   "search": "You look for the trick — is something targeting you?",
   "find":   "It clicks: when your lane is slow you're passed for minutes; when fast you overtake in seconds.",
   "take":   "The cost: every losing moment sticks, so memory says the other lane always wins.",
   "change": "Same traffic tomorrow — but now you see the wave, and it stops fooling you."
 },
 "visual_metaphors": ["two lane lines that morph into conveyor belts", "coral streaks peeling off passing dots and stacking into a memory column", "camera locked to one amber car"],
 "needs_stats": false,
 "status": "pending"}
```

**Ереже:**
- **Story Circle толық болуы керек** — 7 өрістің бәрі бір сөйлеммен. `you`/`need`
  көрерменге тиесілі, `find` — нақты механизм, `take` — иллюзияның бағасы,
  `change` — callback.
- Механизммен түсіндіріледі, сандарсыз (`needs_stats: true` болса — қабылданбайды не қайта жазылады).
- Сызық-адам + абстракт пішінмен көрсетуге келеді (нақты бренд/жер/бет емес).
- Күнделікті, таныс — көрермен "мұны байқағам" десін.
- Қайталанбау: бар `topics.done.jsonl` + `topics.pending.jsonl` тізіміне тексеру.
- Кластерлер: queues & waiting · pricing & incentives · traffic & crowds · rules
  & defaults · platforms & algorithms · institutions & bureaucracy · nature &
  emergent order · game theory in daily life.

### Стартер батч (алғашқы ~20)

1. Why the other lane always looks faster
2. Why elevators skip your floor (кіріктірілген мысал — эталон)
3. Why boarding a plane is slower than it should be
4. Why the popcorn costs more than the movie ticket
5. Why free refills make business sense
6. Why supermarket milk is at the very back
7. Why your flight was overbooked on purpose
8. Why traffic jams appear with no crash or cause
9. Why "please hold" music exists
10. Why gyms sell more memberships than they can fit
11. Why printer ink costs more than the printer
12. Why every queue you join is the slow one
13. Why restaurants put the second-cheapest wine in the sweet spot
14. Why sidewalks form desire paths across the grass
15. Why buses bunch up in twos and threes
16. Why "limited time offer" never really ends
17. Why the crosswalk button often does nothing
18. Why open-plan offices got quiet, not loud
19. Why streaming services keep raising prices together
20. Why the last slice of pizza always sits untouched

---

## 6. Метадерек шаблондары (`config/channel.json` → `30_upload.py`)

**Тақырып (title):** `{title_working} — Invisible Systems`
(60 таңбаға дейін; hook-сұрақ форматы жақсы CTR береді)

**Сипаттама (description):**
```
{one_sentence_takeaway}

Every day you move through systems you never see. Invisible Systems makes one
of them visible in 60 seconds.

#shorts #{cluster_tag} #systemsthinking #howitworks

Chapters and sources for this topic: [—]
```

**Тегтер:** invisible systems, systems thinking, how it works, game theory,
incentives, everyday economics, explained, stick figure animation, 60 seconds,
{system-specific 3–5 тег}

**Категория:** 27 (Education). `selfDeclaredMadeForKids: false`.
`defaultLanguage: en`, `defaultAudioLanguage: en`.

---

## 7. Кадr + жариялау режимі

- Каденция: бастапқыда **күніне 1** (Task Scheduler). Тұрақталса 2-ге көтеру
  (YouTube API квотасы ~6/тәулік жүктеуге жетеді).
- **Тексеру қақпасы:** барлығы `private` жүктеледі. `40_review.py` тізім береді,
  `final-subbed.mp4` ашады. Сіз мақұлдағанын ғана `public` / `publishAt`.
- Алғашқы ~20 видео — 100% адам қарайды. Сапа тұрақталса ғана автопуб талқыланады.
- Формат әртүрлілігі: hook түрін, камера қозғалысын, метафораны ротациялау —
  "жаппай өндіріс" саясат тәуекелін азайту үшін.

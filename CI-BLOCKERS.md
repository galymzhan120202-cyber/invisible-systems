# GitHub Actions Cron — бөгеттер тізімі

**Мақсат:** `auto-channel` конвейерін GitHub Actions-та cron бойынша адамсыз
жүгірту: тақырып → storyboard + animation.html → рендер → дауыс → микс → mux →
verify → YouTube-қа `private` жүктеу → Telegram хабар → кезекті жаңарту.

**Қазіргі күй (2026-09-03):** жергілікті бір видео қолмен жасалып, verify PASS
болды; YouTube OAuth + Telegram қосылды. Бірақ CI-ге дейін төмендегі бөгеттер бар.
Реті — шешу кезегі бойынша (A→H).

---

## A. Репозиторий / бастапқы код

| # | Бөгет | Шешу жолы |
|---|---|---|
| A1 | `auto-channel` — git репозиторийі емес. `.git` жоқ, commit жоқ, remote жоқ. | `git init`, алғашқы commit. |
| A2 | GitHub репо жоқ. **Private болуы міндетті** — `channel.json` (handle, ниша), видео дереккөздері, канал тарихы бар. Public болса "жаппай контент" тексерісін де тартады. | `gh repo create ... --private`. |
| A3 | `.gitignore` қазір build артефакттарын + барлық құпияны + `videos/**/*.mp4` алып тастайды. CI-ге не commit болатынын шешу керек: дереккөздер (storyboard.md, animation.html, narration.json, sfx-cues.tsv) — иә; ірі mp4 — жоқ. | `.gitignore`-ды CI сценарийіне қарай нақтылау; mp4 → Actions artifact. |
| A4 | `stickman-video-director*` — жеке `.git`-і бар екі анықтама репо. CI жобаның ішінен ғана оқуы керек. | `produce.ps1` + `lib/` `auto-channel`-дің ішінде өзіндік екенін тексеру; сыртқа шықса — vendored көшірме. |

## B. Жетпейтін пайплайн коды (нағыз олқылық)

| # | Бөгет | Шешу жолы |
|---|---|---|
| B1 | **`20_produce.py` оркестраторы жоқ.** Тақырып → бума → AI-агент → `produce.ps1` тізбегі ешнәрсемен байланбаған. `produce.ps1` дайын `animation.html` + `narration.json` + `sfx-cues.tsv` талап етеді. | `20_produce.py` жазу — негізгі жұмыс. |
| B2 | **AI-агент қадамы.** PLAN §2.2: видео бумасында `claude -p` headless немесе Codex skill жүгіртіп storyboard.md + animation.html + narration.json жаздыру. CI-де `claude` CLI жоқ (орнату + `ANTHROPIC_API_KEY` керек). Балама — `llm_router.py` (Gemini), бірақ ол қазір тек бір `complete()` мәтін қайтарады: көп файлды авторлау, `window.__seek/__ready/__duration` контрактін тексеру, рендер қатесінде қайта жазу — жоқ. | "author" драйверін жазу: көп файл + контракт валидациясы + retry. |
| B3 | `animation.html` контракті мәжбүрленбейді. `window.__ready/__seek/__duration` ашпаған HTML үнсіз қара/қатып қалған видео береді. | Рендерге дейін валидация қақпасы (headless-та `__duration` тексеру). |
| B4 | `10_suggest_topics.py` жоқ. Кезек қолмен толтырылған (19 тақырып ≈ 3 апта), бастапқыда бөгемейді, бірақ cron таусады. | Топик генераторын жазу (CHANNEL-CONCEPT §5). |
| B5 | `40_review.py` жоқ. Review gate — қасақана қолмен. Cron `private` жүктейді, адам бәрібір `public` жасайды → cron ≠ толық автоном канал. | `40_review.py` жазу; авто-жариялау кейін бөлек шешіледі. |
| B6 | `run_daily.ps1` жоқ — PLAN-дағы бірыңғай кіру нүктесі. CI-ге бір команда керек. | `run_daily` жазу: топик ал → produce → verify → upload → notify → кезек жылжыту. |
| B7 | Идемпотенттік жоқ. Жүктеуден кейін, кезек жаңарудан бұрын қате болса — қайта жүгіру екі рет жүктейді. | Транзакциялық кезек + "`youtube.json` бар → upload аттап кету". |
| B8 | `topics.failed.jsonl` PLAN-да бар, бірақ ешбір скрипт жазбайды. verify қатесі ешқайда бағытталмайды. | Қате жолын қосу: verify FAIL / author FAIL → `topics.failed.jsonl` + себебі. |

## C. Платформа / ОЖ сәйкессіздігі

| # | Бөгет | Шешу жолы |
|---|---|---|
| C1 | Бүкіл produce тізбегі — **PowerShell + Windows**: `produce.ps1`, `mix_audio.ps1`, `mux_video.ps1`, `verify_video.ps1`, `burn_subtitles.ps1`. `settings.json` + `produce.ps1`-де hardcoded `C:\Users\AMINA\...python.exe`. | Төмендегі 3 нұсқаның бірі. |
| C2 | Runner таңдау: **(а)** `windows-latest` — .ps1 жұмыс істейді, бірақ ~2× минут, әрі ffmpeg/Python 3.13/Playwright+Chromium/edge-tts/node орнату керек. **(ә)** `ubuntu-latest` + `pwsh` (PowerShell Core runner-де бар) — .ps1 Windows-only cmdlet болмаса жүреді, ffmpeg apt-тан, арзан; әр скриптті аудит керек. **(б)** .ps1 көмекшілерін Python-ға көшіру — ең тұрақты, ең көп жұмыс. | Ұсыныс: (ә) немесе (б). |
| C3 | Hardcoded жолдар. `settings.json.python` → `python`/`sys.executable`; `produce.ps1 $py` солай. | Конфиг/env-ке ауыстыру. |
| C4 | `render_seek.py` Playwright қолданады. CI-де `playwright install --with-deps chromium` (~300 МБ, кэштеуге келеді). | Workflow-да cache қадамы. |
| C5 | `edge-tts` рендер кезінде Microsoft endpoint-іне барады — желі тәуелділігі, кейде rate-limit/қате. Дауыс `en-US-AvaNeural` қолжетімді болуы керек. | `generate_voiceover.py`-ге retry/backoff. |
| C6 | Детерминизм. Linux headless Chromium мәтін/эможи-ні Windows-тан өзгеше рендерлейді. "Экранда мәтін жоқ" болғандықтан тәуекел төмен, бірақ белгіше эможилері өзгеше шығуы мүмкін. | Алғашқы CI рендерін көзбен тексеру. |

## D. Құпиялар

| # | Бөгет | Шешу жолы |
|---|---|---|
| D1 | 4 құпия файл, бәрі gitignored, ешбірі commit болмайды: `client_secret.json`, `youtube_token.json` (refresh token), `telegram.json`, `keys.env` (Gemini — **әлі жасалмаған**). | GitHub Actions Secrets-ке салу. |
| D2 | CI-ге әрқайсысын Secret ретінде беріп, runtime-да `secrets/`-ке қайта жазатын workflow қадамы керек. Жаңа жолдарды сақтау үшін base64. | `echo "$SECRET" | base64 -d > secrets/...`. |
| D3 | `youtube_token.json`-да **refresh token** бар — ең үлкен қауіп. Репоға жазу қатынасы бар кез келген адам не зиянды workflow PR оны ұрлап каналға пост жасай алады. | Private репо; `pull_request` триггерін шектеу; environment protection; `permissions: contents: read` (қажет жерден басқа). |
| D4 | Токен жаңару. Google client access token-ды refresh token-мен авто-жаңартып `youtube_token.json`-ды **қайта жазады**. CI-де ол жазу эфемерлі. Refresh token тұрақты (prod app), сондықтан әр жүгіріс Secret-тен қайта refresh жасайды. Бірақ Google refresh token-ды ротацияласа — CI жаңасын сақтай алмайды → үнсіз істен шығу. | `if: failure()` → Telegram ескерту; айлық "токен тірі ме" canary. |
| D5 | Gemini free-tier квотасы (RPM/RPD). Күніне 1 видео — жеткілікті. `llm_router` cooldown күйі (`logs/llm_state.json`) CI жүгірістер арасында сақталмайды. | Қабылдауға болады; кеше 429 болғаны есте қалмайды, сол ғана. |

## E. Жүгірістер арасында сақталуы керек күй

| # | Бөгет | Шешу жолы |
|---|---|---|
| E1 | `queue/topics.pending.jsonl` + `topics.done.jsonl` **әр жүгірісте өзгереді** (тақырып pending→done). CI-де workflow жаңартылған кезекті репоға `git commit` + `git push` жасауы керек — өзін-өзі commit жасайтын workflow. `contents: write` рұқсаты + `[skip ci]` қорғанысы керек (цикл болмас үшін). | Workflow соңында commit+push қадамы. |
| E2 | `videos/<slug>/` дереккөздері (storyboard.md, animation.html, narration.json, youtube.json) — оларды да commit жасау керек, әйтпесе не жасалғаны жоғалады. Ірі mp4 → Actions artifact (90 күн) немесе тастау. | Дереккөздерді commit, mp4-ті artifact-қа. |
| E3 | Concurrency. Екі жоспарлы жүгіріс қабаттасса (баяу жүгіріс + келесі cron) екеуі де кезекті өзгертіп push-та конфликт береді. | Workflow-да `concurrency:` group — сериялау. |
| E4 | `logs/*.log` CI-де эфемерлі. | Actions run логі + Telegram-ға сүйену. |

## F. YouTube / саясат / квота

| # | Бөгет | Шешу жолы |
|---|---|---|
| F1 | Квота: 1 жүктеу ≈ 1600 бірлік, 10 000/тәулік → ~6/тәулік шек. Күнделікті cron — жеткілікті. Retry дауылы квотаны жеп қоюы мүмкін. | Жүктеу retry-ын шектеу. |
| F2 | Жаңа канал: алғашқы күндері ~15 жүктеу/тәулік шегі, телефон растау (канал бар болғандықтан өтілген), таралым шектеулі. | Ескерту ретінде. |
| F3 | **Саясат тәуекелі** (PLAN §6.6): жаппай, қайталанатын, "жасанды" контент монетизацияланбайды әрі жойылуы мүмкін. PLAN алғашқы ~20 видеоны адам қарауын міндеттейді. `private` жүктейтін cron — жарайды (адам бәрібір қақпа). **Кез келген авто-жариялау — нағыз тәуекел.** | "Авто" қай жерде тоқтайтынын шешу. |
| F4 | OAuth "unverified app" + sensitive scope: 100-қолданушы шегі (маңызсыз, 1 қолданушы). Google белгілесе қайта рұқсат керек болуы мүмкін. | Ықтималдығы төмен; failure ескертуі жетеді. |
| F5 | Жүктеу метадерегі әр тақырыпқа нақты `takeaway` талап етеді — қазір әдепкі мәні тақырып атауы. | Топик схемасына `takeaway` өрісін қосу. |

## G. Жоспарлау / эксплуатация

| # | Бөгет | Шешу жолы |
|---|---|---|
| G1 | GitHub `schedule:` cron — UTC, әрі best-effort: жүктеме кезінде 5–30+ мин кешігеді, репо 60 күн бос тұрса автоматты өшеді. | E1-дегі өзін-өзі commit оны тірі ұстайды. |
| G2 | Ескерту жоқ. | Workflow соңында `if: failure()` → Telegram "pipeline failed, run <url>". |
| G3 | Құн: `windows-latest` 2× минут. Күнделікті ~3–6 мин жүгіріс — 2000 тегін минут/айға түк емес, бірақ кэшсіз Playwright/Chromium орнату минут қосады. | Chromium-ды кэштеу. |
| G4 | PLAN §6.4 "апталық auth еске салу" — енді маңызсыз (prod app, 7 күндік ескіру жоқ). Бірақ айлық "refresh token тірі ме" canary пайдалы. | Айлық canary workflow. |

## H. Детерминизм / сапа (жұмсақ бөгеттер)

| # | Бөгет | Шешу жолы |
|---|---|---|
| H1 | Жасалған `animation.html` сапасы әркелкі (PLAN §6.3). Адамсыз = бұзылған анимацияны жүктеуге дейін ешкім ұстамайды (дегенмен `private` түседі). `verify_video.ps1` қара кадр / ұзақтық / LUFS ұстайды, "анимация ұсқынсыз/мағынасыз" дегенді ұстамайды. | Алғашқы ~20-да адам қарауы (PLAN талабы) — cron тек `private`-қа дейін. |
| H2 | Story Circle енді міндетті емес (бүгінгі шешім). Author промпті / топик схемасы 7 `circle` өрісін қатаң талап етпеуі керек. | Топик схемасы + author промптін жаңарту. |

---

## Ұсынылатын рет

1. **B1 `20_produce.py` + B2 author драйвері** — жергілікті, CI-сіз. Бір толық
   тақырып→видео→`private`-жүктеу жүгірісін жасау.
2. **B5 `40_review.py` + B6 `run_daily`** — жергілікті ағын толық.
3. **C2/C3** — платформа шешімі: `pwsh` on ubuntu немесе .ps1→Python.
4. **A1–A3** — `git init` + private репо + `.gitignore` нақтылау.
5. **D1–D3 + E1–E3** — Secrets + өзін-өзі commit жасайтын workflow.
6. **G2 + G4** — failure ескертуі + canary.
7. Тек содан кейін — `schedule:` cron қосу.

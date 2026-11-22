# Health Buddy

A nutrition coach for Indian families. One login manages the whole household: log what each
person ate by typing it in English or Telugu, photographing the plate, scanning a packet's barcode
or picking from a list, then see calories, protein, carbs, fat and fibre next to steps and sleep from
Health Connect, with a few careful suggestions each week.

The AI only names foods and portions. Every number (nutrients, BMR, targets, safety floors) comes
from a food database and plain, tested code.

## What works today

- **Accounts and family:** email and password sign-up with a health-data consent screen, family
  members (including children, with a parent/guardian consent checkbox), JSON data export and
  account deletion.
- **Meal logging four ways:** free text (English, Telugu script or Telugu in English letters),
  plate photo (Gemini vision), barcode (camera via the browser's `BarcodeDetector`, or typed digits,
  looked up on Open Food Facts), and search over 1,051 foods. Every method ends on the same review
  list; nothing is saved until you confirm, and the server recomputes nutrients itself.
- **Day view:** calorie ring against the member's target, protein/carbs/fat/fibre, steps, sleep,
  active calories and heart rate, meals by slot. **Family overview:** everyone's day at a glance.
- **Weekly coach:** suggestions grounded only in that member's numbers, filtered for medical
  language, with fixed caution notes for children, pregnancy and very low intake.
- **Health Connect sync API** for the Android companion (`POST /sync/health-connect`,
  idempotent by record id). The dashboard currently shows seeded sample data, labelled as such.
- **English and Telugu UI** from message files, light and dark themes, mobile-first PWA.

## Architecture

```
 Browser (Next.js 15 PWA)  ──/api/*──▶  FastAPI  ──▶  SQLite (Postgres-ready SQL)
   English / Telugu UI       rewrite        │
                                            ├─▶ Gemini (fallback chain): names foods + portions only
                                            ├─▶ Food DB: INDB + USDA basics + curated Telugu aliases
                                            ├─▶ Open Food Facts: one product per barcode, cached
                                            └─▶ nutrition.py: grams, nutrients, BMR, targets (no AI)
 Android companion (planned, Expo) ──POST /sync/health-connect──▶ FastAPI
```

| Path | What it does |
|---|---|
| `api/healthbuddy/parse.py` | Meal text/photo to items. Gemini with a Pydantic schema, `temperature=0`, user text fenced as data. Falls back to a rules parser when AI is off or rate limited, and says so in the UI. |
| `api/healthbuddy/foods.py` | Search and name resolution over English, Telugu script and Romanised names (exact, segmentation, fuzzy). |
| `api/healthbuddy/nutrition.py` | Grams from household units, nutrients, Mifflin-St Jeor BMR, activity multipliers, targets and safety floors. |
| `api/healthbuddy/coach.py` | Weekly stats in SQL, flags by rule, wording by Gemini, then a banned-word filter and code-added cautions. |
| `api/healthbuddy/gemini.py` | Model fallback chain (`GEMINI_MODELS`, default `gemini-3.6-flash,gemini-3.5-flash,gemini-3.1-flash-lite`); 404/429/5xx move to the next model. |
| `api/healthbuddy/api.py` | Routes: auth, family, foods, meals, day view, coach, Health Connect sync, export, delete. |
| `web/src` | Next.js App Router pages, `messages/en.json` and `messages/te.json`, design tokens from [DESIGN.md](DESIGN.md). |

## Nutrition maths (deterministic, tested)

- **BMR:** Mifflin-St Jeor (1990). **Maintenance:** BMR × 1.2 / 1.375 / 1.55 / 1.725 by activity.
- **Goals:** maintain, lose (−500 kcal/day) or gain (+300 kcal/day).
- **Safety floor:** the target never goes below the member's BMR or 1,200 kcal (women) / 1,500 kcal (men).
- **Children (under 18):** no calorie target and no weight-loss goal; Mifflin-St Jeor is an adult equation.
- **Pregnancy:** maintenance only, never a deficit, with a "follow your doctor" note.
- **Protein target:** 0.83 g per kg body weight (ICMR-NIN 2020 RDA for adults).
- **Household measures:** 1 cup = 240 g and 1 glass = 200 ml (INDB `Units.xlsx`); tbsp = 15 ml, tsp = 5 ml.

## Data sources and licences

| Source | Used for | Licence and handling |
|---|---|---|
| [Indian Nutrient Databank (INDB)](https://github.com/lindsayjaacks/Indian-Nutrient-Databank-INDB-), *Current Developments in Nutrition*, 2024 | 1,014 Indian recipes, per 100 g and per household serving | Described as open access, but the repository has no licence file, so it is **not redistributed**: `python -m healthbuddy.foods_build` downloads it at setup into a git-ignored folder. |
| [USDA FoodData Central](https://fdc.nal.usda.gov/), SR Legacy (April 2018) | 33 basic foods (fruit, milk, curd, eggs, nuts, bread, ghee) | Public domain (CC0). The small extract `api/data/usda_basics.csv` is committed. |
| [Open Food Facts](https://world.openfoodfacts.org/) | Packaged food by barcode | ODbL. Looked up one product at a time and cached; never bulk-copied. |
| IFCT 2017 (NIN-ICMR) | Not used | No redistribution grant found. INDB's own values draw on it, which is one more reason INDB isn't committed. |
| `api/data/food_aliases.csv` | 118 curated dishes with Telugu names, Romanised spellings and portion units | Written for this project. |

**Known data limits**
- INDB counts all the frying oil in deep-fried recipes (poori is 738 kcal per 100 g), so those
  items are flagged in the UI as "likely high".
- INDB serving sizes are small (an idli is 25 g, a plain dosa 36 g). They are used as published.
- Dishes INDB lacks are mapped to the nearest dish and shown as **approximate**: gongura pachadi
  uses tamarind chutney, pongal uses khichdi, pappu uses khatti dal, chicken biryani uses chicken
  pulao, avakaya uses garlic pickle.
- My own portion assumptions: one pakoda = 20 g, a katori of curd = 150 g, and one serving of
  gongura pachadi, tamarind chutney or avakaya = 1 tbsp (15 g).

## Evaluation (measured, not estimated)

`api/evals/meals.json` has 84 labelled meal descriptions with expected foods and portions:

- **Basic set (60):** 20 English, 20 Telugu script, 20 Romanised Telugu. Written alongside the
  alias list, so it shares its vocabulary; treat it as a sanity check, not a held-out score.
- **Hard set (24):** phrasings and spellings the alias list was not built from (full sentences,
  plurals like "idlilu" and "దోసెలు", "no pickle", "half a cup of rice"). The aliases were frozen
  before it was scored.

Expected calories use the same food database, so the calorie error measures the parser only,
not the database against a lab.

| Parser | Set | Item precision | Item recall | Portion within 10% | Calorie MAPE |
|---|---|---|---|---|---|
| Rules baseline | Basic (60) | 0.984 | 0.984 | 0.968 | 3.0% |
| Rules baseline | Hard (24) | 0.894 | 0.933 | 0.889 | 11.1% |
| Gemini | both | not measured yet | | | |

Calorie MAPE by language on the hard set (rules): English 1.8%, Romanised Telugu 18.8%, Telugu
script 19.3%. Most misses are Telugu plural forms and full sentences ("nenu rendu idlilu tinnanu").

The Gemini run hasn't happened yet because the API key in this environment was rejected by Google
("API key not valid"). With a valid key in `api/.env`:

```bash
cd api && python -m evals.run --engine gemini   # cached per meal in evals/runs/, paced for the free tier
```

Results are written to `api/evals/results_<engine>.json`, with every miss listed.

## Safety and privacy

- No diagnoses, medicine or dose advice: the coach prompt forbids it, and a filter drops any
  suggestion that mentions medicines, doses, diseases or treatment (English and Telugu terms).
- Caution notes for children, pregnancy and very low intake come from code, not the model.
- Passwords are hashed with argon2id. Sessions are opaque random tokens stored only as SHA-256 hashes,
  in an HTTP-only, SameSite=Lax, Secure cookie (the Android companion gets a bearer token instead).
- Failed sign-ins are limited per email and IP (5 in 15 minutes), plus a looser per-email cap (20)
  that doesn't apply to IPs that have signed in to that account before, and a hard ceiling of 100 that applies to everyone. In production, run uvicorn
  behind one trusted proxy with `--forwarded-allow-ips` set to it so client IPs are real.
- India's DPDP Act 2023: a consent screen at sign-up, parental consent for children, JSON export of
  everything stored, and account deletion that cascades to all family data.
- Meal text and photos go to Google Gemini to identify foods; the consent screen says so.
  Third-party product names from Open Food Facts are never put into the coach prompt.

## Run it locally

Requirements: Python 3.11+ and Node 20+.

```bash
# API
cd api
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                              # add GEMINI_API_KEY (an AI Studio key, starts with AIza)
python -m healthbuddy.foods_build                 # downloads INDB, builds data/foods.json
python -m healthbuddy.seed                        # optional demo family; login in .env.example
pytest                                            # 42 tests
uvicorn healthbuddy.api:app --port 8000

# Web (second terminal)
cd web
npm install
npm run dev                                       # http://localhost:3000, proxies /api to :8000
```

Without a Gemini key, typed meals use the rules parser, the coach uses rule templates, and photo
logging is unavailable; the UI says which engine was used.

## Android companion (designed, not built)

Android Studio, a JDK and adb aren't installed on the development machine, so the companion is a
design only.

- **Stack:** Expo (React Native) with a development build and `react-native-health-connect`.
- **Permissions:** read Steps, SleepSession, ActiveCaloriesBurned and HeartRate, requested in-app
  with a plain explanation, and revocable.
- **Auth:** `POST /auth/token` with email and password returns a bearer token, kept in
  `expo-secure-store`.
- **Sync:** the user picks which family member the phone belongs to. A background task
  (`expo-background-fetch`, about every 30 minutes) reads records changed since the last sync token
  and posts them to `/sync/health-connect` in batches of up to 1,000:
  `{member_id, records: [{id, type, start, end, value, unit}]}`.
  - `id` is Health Connect's `metadata.id`, so re-sending is safe: the API counts records as
    inserted, updated or unchanged.
  - Timestamps carry a UTC offset. Sleep is counted on the day you wake up.
- **Offline:** unsent batches queue locally and retry with backoff.

## Honest limits

- No real users have tried it; everything was tested with seeded or synthetic data.
- Each account's family lives under one login. Adult members can't yet link their own accounts.
- Portion sizes from photos are the model's guess; the review step exists because they will be off.
- Barcode camera scanning needs a browser with `BarcodeDetector` (Chrome on Android). Others type
  the digits.
- Login throttling and caches are in process memory, fine for one server and not for several.
- SQLite for development; the SQL is plain enough to move to Postgres, but that hasn't been done.

## Tests

`api/tests`: nutrition maths (BMR, floors, child and pregnancy rules, units), parser schema and
rules parsing in three scripts, auth (hashing, cookie flags, throttling), family permissions,
server-side nutrient recompute, Health Connect sync idempotency and validation, export and delete,
and coach behaviour (full days only, cache invalidation, safety filter). The web app is checked
with `npm run build` (type-check and lint).

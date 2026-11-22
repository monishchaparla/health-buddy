# Health Buddy: Design System

Format follows the awesome-design-md convention so humans and coding agents build the same product.

## Overview

Health Buddy is a nutrition coach for Indian families. One adult (usually the person who plans the
household's meals) logs what each family member ate, by typing it in English or Telugu, taking a
photo of the plate, scanning a packet's barcode or picking from a list. Health Buddy turns that into
calories, protein, carbs, fat and fibre, shows it next to steps and sleep from Health Connect, and
writes a few careful suggestions each week.

The interface takes its cue from the steel thali and tiffin found in almost every Indian kitchen:
cool, clean, washable surfaces, with colour coming from the food. It should feel like a calm
household tool used one-handed in a kitchen, not a fitness app.

**Key characteristics**
- Cool stainless-steel neutrals. No cream, no pure black.
- One action colour (indigo). Turmeric is spent on one thing: the calorie ring.
- One family, **Anek Telugu**, for both English and Telugu, so mixed-script lines sit on one baseline.
- The day's thali ring is the single bold element. Everything around it stays quiet.
- Mobile-first, thumb-reachable primary action, system light/dark with a manual toggle.

## Colors

### Light
| Token | Hex | Use |
|---|---|---|
| `canvas` | #EDF0F3 | Page background (steel) |
| `surface` | #FFFFFF | Panels, list rows, sheets |
| `ink` | #1A2333 | Headings, numbers, body |
| `ink-2` | #4A5568 | Secondary text, labels, axis text |
| `rule` | #D5DBE2 | Hairlines, input borders, ring track |
| `indigo` | #3D3A9E | Primary action, links, selection, focus ring |
| `indigo-wash` | #E6E6F7 | Selected tab, chip background |
| `turmeric` | #E2A400 | Calorie ring fill only (never text on white) |
| `turmeric-wash` | #FBF0D2 | Caution notes background |
| `turmeric-ink` | #6B4B00 | Text on turmeric wash |

### Dark
| Token | Hex |
|---|---|
| `canvas` | #10141B |
| `surface` | #171C25 |
| `ink` | #E6EAF0 |
| `ink-2` | #A2ACBA |
| `rule` | #2A3242 |
| `indigo` | #A9A7F2 (button fill; label uses `canvas`) |
| `indigo-wash` | #26254A |
| `turmeric` | #F2BE3A |
| `turmeric-wash` | #3A2F12 |
| `turmeric-ink` | #F6D98A |

### Data (charts and macro chips only)
| Series | Light | Dark |
|---|---|---|
| Protein | #3D3A9E indigo | #A9A7F2 |
| Carbs | #B98500 deep turmeric | #F2BE3A |
| Fat | #A8436B kokum | #E28AAE |
| Sleep | #5B6B8C dusk | #9AA9C9 |

### Status
Over target and errors use kokum text (#A8436B light, #E28AAE dark) with a word, never colour alone.
Caution notes (children, pregnancy, see a doctor) use `turmeric-wash` with `turmeric-ink` text and an icon.

Contrast: `ink` and `ink-2` on `canvas` and `surface` pass WCAG AA (≥ 4.5:1) in both themes;
white on `indigo` and `canvas` on dark `indigo` pass AA for button labels.

## Typography

- Family: **Anek Telugu** (Google Fonts, OFL; Latin and Telugu in one variable family, 400–600).
- Numbers: `font-variant-numeric: tabular-nums` wherever numbers line up.
- Scale (px): 13 caption, 15 UI, 17 body, 20 section title, 26 page title, 40 ring figure.
- Weights: 400 body, 500 UI and labels, 600 page titles and the ring figure.
- Telugu text gets line-height 1.6 (vowel signs need room); Latin body 1.5.
- Sentence case everywhere. No all-caps labels, no monospace labels.

## Layout

- Mobile-first: single column, 16px side gutters, max content width 640px, centred on large screens.
- Spacing base 4px; common steps 8, 12, 16, 24, 32.
- Top bar: app name left, language and theme toggles right.
- Bottom navigation on phones (Today, Log, Family, Settings); the same bar stays at the bottom
  on larger screens, centred to the content width.
- Day view order: member and date → thali ring → macro katoris → steps and sleep strip →
  meals list → coach suggestions.
- Family overview: one row per member with today's kcal against target and a mini ring.
- Text left-aligned; numbers right-aligned in lists.

## Elevation and shape

- Flat. Surfaces separate by tone (`surface` on `canvas`) and a 1px `rule`, not shadow.
- Radius: 10px controls, 16px panels, full for chips, avatars and the ring.

## Components

- **Thali ring:** 200px SVG ring. Track in `rule`, fill in `turmeric`, rounded cap. Centre shows
  kcal eaten (40px, 600) and "of 1,900 kcal" (13px, `ink-2`). Over target: the ring is full and a
  kokum label "220 kcal over" appears under it. Children and pregnancy: no deficit target, with a
  caution note.
- **Macro katoris:** three small circles under the ring (protein, carbs, fat) with grams and a
  thin arc in the series colour.
- **Buttons:** primary is `indigo` fill with white label (dark: `canvas` label); secondary is
  `surface` with a `rule` border. One primary per screen. Labels are verbs ("Log meal", "Add member").
- **Log meal:** four tabs (Type, Photo, Barcode, Search). Every method ends on the same review
  list: item, portion stepper, grams, kcal, with "approximate match" shown when the food database
  used the nearest dish. Nothing is saved until "Save meal".
- **Caution note:** turmeric wash panel with an info icon, one or two sentences.
- **Inputs:** 44px tall, `rule` border, 10px radius, label above, error text below in kokum.
- **Focus:** 2px `indigo` outline with 2px offset on every interactive element.

## Motion

- The thali ring fills once on load (600ms ease-out). That is the only non-triggered motion.
- `prefers-reduced-motion`: no ring animation.

## Voice

- Plain, warm, specific. "Add a meal for Amma", not "Create a meal entry".
- Never diagnose, never mention medicines or doses. When something needs a professional, say
  "talk to a doctor or dietitian" plainly.
- Errors say what happened and what to do: "Couldn't read that photo. Try again in better light,
  or type the meal."
- English and Telugu strings live in message files; no hard-coded UI text.

## Do and don't

| Do | Don't |
|---|---|
| Keep turmeric for the calorie ring | Use turmeric for buttons or text |
| Show "approximate" when a dish was matched to its nearest neighbour | Present a guessed value as exact |
| Show grams next to every portion | Hide the portion behind "1 serving" |
| Use words with colour for status | Signal over/under with colour alone |

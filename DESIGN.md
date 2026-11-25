# FM27 Companion: Mac app design rules

In code: `DS` in `mac/SquadReport/Views/Components/DesignTokens.swift` (spacing, radii, surfaces, deltas, tile sizes)
and `Meter`.

These are strict rules for `mac/`. They come from `REFERENCE_AUDIT.md`: Linear for surfaces, hairlines and rows;
TradingView for dense numbers, deltas and panel balance; TablePlus for tables.

A value that isn't in this file needs a one-line code comment saying why. Looks (`Theme`) may change **colours and
display faces** through these tokens. They may **not** change the spacing scale, radii, row heights or page
template.

Colour tokens below are for the dark looks (Original in dark mode, B Floodlit, C Scoreboard, E Glass + scoreboard).
The light look (D Sticker) keeps its own colour values but follows every other section. A Programme is dark now
(dark newsprint `#121211`, light print rules `#EDEDE6`).

---

## 1. Colour tokens (dark)

### Surfaces: neutral, no tint, ~× 1.8 luminance per step
| Token | Hex | Use |
|---|---|---|
| `surface.canvas` | `#0B0B0D` | window background. The sidebar keeps the system's grey sidebar material (his choice, 25 Nov 2026) |
| `surface.panel` | `#151517` | cards, tiles, the hero, the table body |
| `surface.raised` | `#1E1E21` | group headers, table header, hover on a card or row |
| `surface.selected` | `#26282B` | selected row (no accent), meter track, pressed |
| `border.hairline` | `#26272A` | the one 1 pt edge on cards and dividers |
| `border.strong` | `#34363A` | focus-free emphasis edge (the active filter tile) |
| `zebra.alt` | `#18181B` | the alternate table row on `surface.panel` (ΔY ≤ 0.005) |

### Text
| Token | Hex | Use |
|---|---|---|
| `text.primary` | `#EDEDEF` | names, values, titles |
| `text.secondary` | `#A0A1A6` | labels, subtitles, column headers |
| `text.tertiary` | `#6C6D72` | IDs, captions, empty stars, caps section labels |
| `text.disabled` | `#48494D` | disabled only |

### Accent and meaning
| Token | Hex | Use |
|---|---|---|
| `accent.fill` | `#1C7F46` | selected sidebar row, primary button, active segment. Always white text on it |
| `accent.text` | `#4FC77F` | the one green for text, lines and meters on dark |
| `delta.up` | `#4FC77F` | good numbers, won (W) |
| `delta.down` | `#F2555A` | bad numbers, lost (L), "Needs a better starter" |
| `delta.flat` | `#8E9096` | drawn (D), unchanged |
| `warn` | `#F5A524` | "Ageing starter", "Needs more depth", weak-in-one-phase |
| `rating.star` | `#E9B949` | filled stars, in every dark look. Empty stars are `text.tertiary` |
| `club.kit` | from the report | slot headers on the pitch, the club dot. Nowhere else |

- **Status colours stay as they are in `Palette.swift`.** These are transfer in/out, loan in/out, injury
  short/long, suspended and arranged. Statuses must stay visually distinct (his rule), and nothing above
  replaces them.
- **Ratings aren't good/bad:** stars are gold, never `delta.up` green.

---

## 2. Spacing scale

**`4 · 8 · 12 · 16 · 20 · 24 · 32 · 48`**. Nothing else in layout code.

- **Micro values:** `2` and `6` are allowed **only inside badges and pills** (their own padding).
- **Page inset:** `24` on all four sides, on every page.
- **Section gap:** `32` between sections. `12` between a section title and its content.
- **Grid gap:** `12` between cards and tiles.
- **Card padding:**
  - `20` for KPI tiles and the hero;
  - `16` for content cards (verdicts, positions, tactic cards);
  - `12` for compact cards.
- **Inside a row:**
  - `8` between an icon and its label;
  - `12` between adornments;
  - `16` before a right-aligned numeric column.

## 3. Row heights

| Row | Height | Pitch | Notes |
|---|---|---|---|
| Table row (Squad list, Stats) | 24 | 24 | `zebra.alt` alternate, no dividers |
| Sidebar row | 28 | 29 | selection inset 8 pt from the sidebar edges, radius 6 |
| List row (Positions, Sandbox roster) | 28 | 28 | no zebra, hairline-free |
| Numeric watch row (leaders, form lists) | 30 | 30 | TradingView-style |
| Rich row (verdict people, transfers) | 44 | 44 | two lines max |
| Toolbar and segmented controls | 28 | – | |

## 4. Corner radii

**`4 · 6 · 10 · 14`, plus capsule.** Nothing else (no 2, 3, 5, 7, 8 or 16).

| Radius | Use |
|---|---|
| 4 | badges, status pills, form chips (W/D/L), familiarity letters |
| 6 | buttons, segmented controls, selected rows, inputs |
| 10 | cards, tiles, panels, popovers' inner content |
| 14 | containers that hold radius-10 cards with 4 pt between edges (`outer = inner + padding`) |
| capsule | filter tabs only (Linear's Active / Backlog pattern) |

All corners are `.continuous`. The pitch keeps the look's `pitchRadius`.

## 5. Typography

- **Faces:**
  - **UI and data:** SF Pro (system).
  - **Every number in a table, tile or row:** `.monospacedDigit()`, so columns align on the decimal.
- **Display face** (the look's): only for the page title, section titles and the hero club name.
- **Two faces per screen at most:** system plus the look's display face.
- **Doto (dot-matrix)** is allowed in exactly one place: the decorative league position in the Home hero, at 44 pt
  or more. **Never** in tiles, tables, Tactical fit or anything you read as data.

| Role | Size / weight | Colour |
|---|---|---|
| Hero club name | 48, display, heavy | primary |
| Page title | 28, display, bold | primary |
| Section title | 20, display, bold | primary |
| KPI value | 34, system, semibold, mono digits | primary |
| Card title | 15, system, semibold | primary |
| Body / row | 13, system, regular (names medium) | primary |
| Label / column header | 12, system, regular | secondary |
| Caption / sub | 11, system, regular | tertiary |
| Caps section label | 11, semibold, +0.06 em tracking | tertiary |

- **One display size per block:** nothing at 34 or above may sit next to another element at 34 or above.
- **Labels sit at least two scale steps below their values** (12 under 34, 11 under 20).

## 6. Components

### Page template (every page)
- **Row 1:** the page title (28) with a 13 pt secondary subtitle on the same baseline, at the page inset.
- **Row 2:** the page's primary control (segmented, chips or the filter), left-aligned, 28 pt tall. Its width is
  set by its content, or it spans the full width. It's never a stray fixed width.
- **Row 3 and on:** content.
- The window title shows the page name, and the subtitle "Club · date". Nothing on the page repeats either.

### KPI tile (TradingView detail block)
- Height **148**, padding 20 (20 + label 15 + 8 + value 41 + 8 + slot 14 + 8 + sub 14 + 20).
- **Exactly four rows:** label (12) / value (34) with its unit on the same baseline / a 14 pt slot holding a 6 pt
  meter or a star row / sub (11).
- A tile with nothing for the slot **keeps the empty 14 pt slot** (`Color.clear`, not `EmptyView`, which collapses),
  so values and subs line up across a row.
- Tiles in a row share one height and one value baseline. Use 2, 3, 4 or 5 per row, always filling the width.

### Meter
- 6 pt tall, radius 3, full content width.
- Track `surface.selected`, fill a meaning colour (`accent.text`, `warn`, `delta.down`). Never grey.
- Two-part values use two fills side by side (TradingView volume).

### Badges: three levels, at most three per row
1. **Needs attention** (injured, suspended, needs a starter): tinted pill, radius 4, 18 pt tall, text in the
   colour, fill at 16 % of it.
2. **Worth knowing** (contract ending, arranged): outline pill, 1 pt at 55 %, no fill (dashed for arranged, as
   now).
3. **Facts** (familiarity N/A, games count, age): plain glyph or tertiary numeral, no box. Linear's `NIT-1` level.

Anything past three per row moves into the hover text or the player card.

### Deltas and form
- **Numbers that go up or down are coloured text** (`delta.up` / `delta.down`), not boxes.
- Form is W/D/L chips 20 × 20, radius 4, filled `delta.up` / `delta.flat` / `delta.down`, white text.

### Cards with a meaning colour
- Use a **3 pt leading bar**, never a full coloured border or a coloured top *and* a coloured pill.
- In a row of cards, sections inside the cards start at the same y. Clamp the body to 2 lines, and the rest goes to
  the hover text.

### Multi-panel pages
- **Two panels:** 65 / 35 (main / side).
- **Three panels:** about 19 / 62 / 19.
- Panels fill to their edges or scroll. **No block may leave more than 48 pt of unexplained empty space** inside
  its container.

### Hero (Home)
- Two columns, **55 / 45**.
- The pitch fills its column's height minus 24 pt. Its frame is never fixed in points.

---

## 7. Don'ts

- **No tinted surfaces.** Surfaces are neutral grey; colour goes in content, not in the canvas.
- **No borders thicker than 1 pt**, and no border plus a shadow plus a fill on one card.
- **No zebra stronger than ΔY 0.005**, and no zebra outside tables.
- **No filled pills for facts.** Only level-1 badges get a fill.
- **No more than one accent colour per region**, and no green for ratings.
- **No two display-size elements side by side**, and no second dot-matrix number anywhere.
- **No spacing, radius or font size outside the scales above.** That includes 1, 3, 5, 7, 10, 14 or 18 as layout
  spacing.
- **No fixed-point frames for content that should fill** (the Home pitch's 460 × 320, fixed-width segmented
  controls).
- **No grey meters, and no meters thicker than 6 pt.**
- **No stuck status text:** a status pill that hasn't changed in 30 s while the engine is fine is a bug.
- **No UI change reported as done before it has been seen running** (see the rule in `CLAUDE.md`).

# Reference audit: Linear, TradingView, TablePlus vs FM27 Companion (25 Nov 2026)

How this was made: window captures through Computer Use (`app_screenshot`, 1 pt = 1 px), then colours sampled
from the captures (5×5 average) with relative luminance **Y** (0 = black, 1 = white). Captures are JPEG and pass
through the display's colour profile, so hex values are within a few steps of the true ones. Treat **ratios** as
the reliable part. Where the app's code has an exact value it is given too.

**Stats Plus is not installed or running on this Mac.** TablePlus (the closest running app) stood in for it, but
TablePlus is a database client with no KPI cards or meters. So the KPI-card section below is built from
TradingView's symbol-detail panel, the only KPI-style block in the captures. Re-run this part if you install
Stats Plus.

FM27 Companion was captured with your real save in the **Scoreboard** look (C) at 1422 × 840 pt. Nothing from
those captures is committed (the repo is public).

---

## 1. Linear (1280 × 800 pt, dark)

### Surface luminance steps
| Surface | Hex | Y | Step vs previous |
|---|---|---|---|
| Window chrome and sidebar (one surface) | `#0E0E12` | 0.0048 | (base) |
| Content panel (raised, rounded, inset 10 pt from the right and 37 pt from the bottom) | `#181818` | 0.0093 | × 1.9 |
| Group header bar ("Todo 4") | `#222225` | 0.0166 | × 1.8 |
| Selected sidebar row | `#272B2D` | 0.0244 | × 1.5 |

- The **sidebar is the darkest surface**, the same as the window chrome. Content sits on a lighter, raised panel.
  The hierarchy reads as "the work is lifted towards you".
- Each step is about **× 1.5–1.9 in luminance**. That gap is small enough to feel like one material and big enough
  to read.
- The palette is a near-neutral grey with a faint cool cast (`#0E0E12`). There's no colour in surfaces at all.

### Hairlines
- A single **1 pt line `#232323` (Y ≈ 0.017)** separates sidebar and panel. Its luminance sits **one step above the
  lighter of the two surfaces** it divides, so it defines the edge without a visible "border".
- Inside the panel there are no row dividers. Rows separate by spacing, and the group header by its fill.

### Sidebar rows
- Sidebar width **265 pt (20.7 % of the window)**.
- Rows are **28 pt tall on a 29 pt pitch** (1 pt gap). Icon 14 pt at 15 pt from the sidebar edge, icon→label gap
  about 8 pt, label 13 pt regular.
- The selection is a **filled rounded rect, radius about 6 pt, inset 12 pt** from the sidebar edges. It isn't
  full-bleed.
- Counts ("1") are **plain secondary numerals**, right-aligned 15 pt from the edge. There's no badge capsule.
- Section labels ("Workspace", "Your teams") are 12 pt secondary with a caret, and sit **about 16 pt above** their
  first row after a gap of about 45 pt from the previous group.

### Priority and status badge hierarchy (compact)
| Level | Example | Treatment |
|---|---|---|
| 1, identity | `NIT-1` | 13 pt, tertiary grey, fixed-width column |
| 2, priority | `---` | glyph only, tertiary, 14 pt box |
| 3, status | Todo ring | 14 pt outline icon, no fill, no text |
| 4, title | "Get familiar with Linear" | 13 pt, primary, medium |
| 5, metadata | avatar, "Nov 25" | right-aligned, secondary, 20 pt from the edge |

- There are **no filled pills in rows at all.** Colour is reserved for one accent (team icon `#EF32A5`).
- Issue rows are 44 pt on a 44 pt pitch. The group header bar is 36 pt tall, radius about 6.
- Filter tabs (Active / Backlog / All issues) are **26 pt capsules**: the active one is filled, the others have a hairline.

---

## 2. TradingView Desktop (1152 × 864 pt)

### Multi-panel grid balance
| Region | Width | Share |
|---|---|---|
| Left tool rail | 52 pt | 4.5 % |
| Chart | ~750 pt | 65 % |
| Right column (watchlist over detail) | 300 pt | 26 % |
| Right icon rail | 46 pt | 4 % |

- The right column splits **55 / 45** (watchlist 470 pt over symbol detail 390 pt).
- Panels are pure black `#000000`. They separate with **`#181818` 1 pt dividers / 4 pt gutters** (Y 0.0096), not
  with different panel colours.
- Nothing floats with dead space. Each panel is filled edge to edge by its content, or scrolls.

### High-density numeric list (watchlist)
- **30 pt row pitch**, no zebra, no row dividers.
- Columns: symbol left-aligned, then **three numeric columns (Last, Chg, Chg%) each ~65 pt and right-aligned** on
  a shared right edge. Digits are tabular, so decimals line up down the column.
- The header row has the same 30 pt pitch, 13 pt secondary. Section labels ("INDICES", "STOCKS") are 11 pt caps
  with tracking, tertiary, with a disclosure chevron.
- Numbers are **coloured as text, not boxed**:
  - down: red, measured `#F65F6E` (TradingView's `#F23645`);
  - up: green, measured `#00917F` (`#089981`).
- On the Last column, only the digits that changed take the colour.

### Colour-coded pills
- Pills are rare and meaningful. Examples: "Open" (green dot + text, tinted fill), "Indicative data" (pink tint),
  and SELL/BUY boxes (1 pt outline in red/blue, two-line, radius about 4).
- The pill height is about 18 pt, radius 4–9. Colour lives in the outline or tint, and the text stays readable on
  black.

### KPI block (symbol detail, used here instead of Stats Plus)
- Label: 12 pt secondary ("Volume", "Avg. volume (30D)").
- Value: 30 pt price with the **delta on the same baseline** at 15 pt in the delta colour ("−13.19 −8.49%").
- **Meter: 6 pt tall, full panel width (268 pt), two-tone** (blue `#3585E4` for today, cyan `#0CC4D4` for the
  average), radius 3, no track gap.
- The news card is `#0E0E0E` on black, radius about 10, 12 pt padding. It's the only card in the whole window.

---

## 3. TablePlus (1320 × 684 pt), standing in for Stats Plus

- **Flat greys, no tint:**
  - sidebar and detail panes `#262626` (Y 0.020);
  - table header `#2C2C2C`;
  - zebra rows `#2D2D2D` / `#313131`.
- The zebra step is only **ΔY 0.0047 (≈ 18 %)**. It's barely there, and helps the eye along a row without banding.
- The rows are **24 pt pitch** with a monospaced data font. **Numbers right-aligned** (`4.5`, `180000`), text
  left-aligned.
- Panes are 250 / 820 / 250 pt (**19 % / 62 % / 19 %**). The bottom bar is 36 pt with a segmented control and a
  "1–3 of 3 rows" count, centred.
- One status colour (the green environment bar `#469E78`) carries meaning for the whole window.
- Its empty states are calm: "No row selected" centred in secondary text. There's no illustration.

What can't be extracted: KPI card proportions, progress meters, and dense readouts kept balanced. TablePlus has
none of these.

---

## 4. FM27 Companion, measured (Scoreboard look)

### Surfaces
| Surface | Measured | Code | Y (measured) |
|---|---|---|---|
| Page canvas | `#0B100B` | `#0A0B0A` | 0.0048 |
| Cards / panels | `#131816` | `#101211` + 1 pt `#232825` stroke | 0.0087 |
| Sidebar (system material) | `#292929` | (system) | 0.0225 |
| Squad table zebra | `#232323` / `#323232` | (system `Table`) | 0.018 / 0.033 |

- **The hierarchy is inverted against Linear.** Your sidebar is the *lightest* large surface (Y 0.0225, about 4.7 ×
  the canvas). Linear's sidebar is the darkest. On a near-black canvas the sidebar reads as a grey slab, and that's
  why the app feels "two apps glued together".
- The canvas→card step (× 1.8) already matches Linear's. Keep it.
- The surfaces carry a **green tint** (`#0B100B`, `#131816`) that the references never have. Next to the green brand
  colour and green stars it makes everything feel green.
- **The squad table zebra is too strong**: ΔY 0.015, three times TablePlus's step. Rows band instead of guide.

### Home
**Header scale**
- "LIVERPOOL" is `heroFont(64)`. Right beside it, "7th" is Doto at **60 pt** (`positionFont(60)`).
- That puts two display-size elements in two different faces in one block, so neither is the hero.
- The labels under them (In-game date / Tactic / Save) are 11 pt at 75 % opacity, and the values 18 pt. That's a
  jump of 64 → 18 → 11 with nothing between.

**Pitch framing**
- The pitch sits in a fixed **460 × 320 pt frame**, but the drawn pitch is only **~283 pt wide (24 % of the
  1165 pt hero)**.
- That leaves **~270 pt of dead space** between the text column (which ends at x 753) and the pitch (which starts at
  x 1022), plus ~90 pt to the right.
- The hero is 378 pt tall and about 40 % empty.

**Club snapshot density**
- There are four tiles of 283 × 138 pt. Tiles 1 and 4 have three lines and tiles 2 and 3 have four, so tiles 1
  and 4 end **24–49 pt above** the others' last line.
  - Tile 1: label / value / sub.
  - Tile 2: label / value / meter / sub.
  - Tile 3: label / value / stars / sub.
  - Tile 4: label / value / sub.
- The heights now match (since the last pass), but the *content* doesn't. Half the row looks empty at the bottom.
- The tile-2 meter is **8 pt tall and grey**. Wage room is a semantic quantity, so it should use the semantic colour
  at a TradingView-style 6 pt.

**"Where the squad needs work"**
- These are three-across cards of 380 pt. Each has:
  - a 4 pt coloured left bar;
  - a rank circle, slot and coloured title;
  - a body of 1–2 lines;
  - then Starter/Backup rows.
- The body lengths vary, so the **Starter rows sit at different heights** across a row of cards. The eye can't scan
  "Starter" across the row.

### Squad list vs Positions vs Tactical fit
| Aspect | Squad list | Positions | Tactical fit |
|---|---|---|---|
| Page title | none (KPI tiles first) | "Position by position", 26 pt display | segmented control first, then "How the tactic is going" |
| Primary control | segmented, 690 pt fixed | key strip | segmented, 555 pt fixed |
| Row style | system zebra, 23 pt | tinted rows (green = natural), 24 pt | cards, 83 pt |
| Status shown as | outline pill ("Contract ends…") | coloured glyph + count square + dashed pill | coloured strip |
| League position | – | – | "7th" Doto 44 pt again |
| Section accent | – | 3 pt coloured top rule + filled status pill | coloured section titles ("What's working" green, "not working" red) |

- **The three pages put their title, their main control and their status language in three different places.**
  None is wrong alone, but together they don't read as one product.
- **Positions rows carry up to seven adornments**:
  - familiarity badge;
  - status glyph;
  - warning triangle;
  - potential dashed pill;
  - games-count square;
  - stars;
  - age.

  Linear's rows carry three at most.
- **Tactical fit columns are uneven**: 5 cards on the left and 6 on the right, so the bottom-left is empty.

### Other things noticed
- **The toolbar status pill has said "Opening your last report" (orange) throughout this capture.**
  - In this state the app is showing the cached report and hasn't yet had a fresh one from the engine.
  - Either the engine isn't serving, or the state is wrong. Your earlier screenshot showed the old banner stuck the
    same way.
  - Worth checking before more design work. I haven't changed any code.
- **The sidebar selection is grey in every capture** because the window was in the background. The new green
  selection only shows when the window is in front, so it couldn't be checked here.

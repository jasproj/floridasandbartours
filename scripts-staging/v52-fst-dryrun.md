# floridasandbartours v5.2 Dry-Run Report — null-price tour re-extraction

**Generated:** 2026-05-03T20:34:46.366Z
**Branch:** `feat/fst-v52-price-extraction`
**Mode:** `--dry-run-only` (no writes to tours-data.json)

## 1. Inputs

- floridasandbartours total tours: 500
- Tours with `price: null` evaluated: **124**
- Extractor: v5.4 baseline + v5.2 dominant-price gate (ported verbatim from wanderusvi)
- Page fetch: Playwright (chromium headless), 1.5 s settle wait

## 2. Result distribution

| Outcome | Count | Disposition |
|---|---:|---|
| **high** (v5.4 Method 1/2 — adult/per-person anchor) | 11 | "From $X" if applied |
| **medium** (v5.4 native — Method 3/4/6) | 15 | "From $X" if applied |
| **medium** (v5.2 dominant-price gate) | 7 | "From $X" if applied |
| **low** (Method 5 unanchored, gate FAILed) | 4 | stays "Check availability" |
| **no-price** (extractor returned null) | 87 | stays "Check availability" |
| **error** (fetch/parse) | 0 | stays "Check availability" |
| **Total** | 124 | |

**Net effect if applied --live:** 33 tours flip from "Check availability" → "From $X" (26.6% of the 124). 91 stay hidden.

## 3. Cat-E candidate sanity check

**0 Cat-E candidates** detected among gate PASSes. Disqualifier blocklist (`additional, extra, option, optional, rental, nitrox, upgrade, supplement, add-on, addon, surcharge` + `+$` literal) appears to be holding.

## 4. Sample 10 promoted tours

### 540929 — TIKI SUNSET AND HARBOR TOURS

- company: Tailfins Island Adventure
- extracted price: **$49** (medium, unknown)
- priceSource: `v52-dominant-gate`
- gate distinct $-values: [44,49]
- gate matched token: `$49.99`
- gate ±40 char window:

  ```
  up to 18) 4.8 stars 1300 Google reviews $49.99 Individual Sunset 2026 $44.99 Individua
  ```
- all $-hits in page: ["$49.99","$44.99"]

### 256293 — Large Private Party Boat

- company: Staying Afloat Party Boat LLC
- extracted price: **$1950** (medium, unknown)
- priceSource: `v52-dominant-gate`
- gate distinct $-values: [1950,3901]
- gate matched token: `$1,950.72`
- gate ±40 char window:

  ```
   Party On! 4.9 stars 904 Google reviews $1,950.72 Two Hour Private Boats $3,901.43 Four H
  ```
- all $-hits in page: ["$1,950.72","$3,901.43"]

### 416362 — Stargazing Boat Tour

- company: Vero Tackle & Watersports
- extracted price: **$300** (medium, unknown)
- priceSource: `v52-dominant-gate`
- gate distinct $-values: [300]
- gate matched token: `$300`
- gate ±40 char window:

  ```
   6 people 4.9 stars 1043 Google reviews $300 Private Tours Up to 6 People Prices for
  ```
- all $-hits in page: ["$300"]

### 307909 — Half-Day Offshore Fishing Charter

- company: Dirty Dolly Fish Company
- extracted price: **$1100** (medium, unknown)
- priceSource: `v52-dominant-gate`
- gate distinct $-values: [1100]
- gate matched token: `$1,100`
- gate ±40 char window:

  ```
  ot Stuart Angler for up to six anglers. $1,100 Private Charters Per Trip • Up to 6 Peo
  ```
- all $-hits in page: ["$1,100"]

### 307914 — Three-Quarter Day Offshore Fishing Charter

- company: Dirty Dolly Fish Company
- extracted price: **$1300** (medium, unknown)
- priceSource: `v52-dominant-gate`
- gate distinct $-values: [1300]
- gate matched token: `$1,300`
- gate ±40 char window:

  ```
   a variety of pelagic and reef species. $1,300 Private Charters Per Trip • 7am-2pm • U
  ```
- all $-hits in page: ["$1,300"]

### 503308 — Manatees & Three Sisters Springs: Kayak Tour + Snorkeling

- company: Kacey's Custom Adventures
- extracted price: **$40** (medium, unknown)
- priceSource: `v52-dominant-gate`
- gate distinct $-values: [40]
- gate matched token: `$40`
- gate ±40 char window:

  ```
  pture all your memorable moments with a $40 value photo package included. Highlight
  ```
- all $-hits in page: ["$40"]

### 668145 — Granada Glow Paddle

- company: Pirate Bay Paddle
- extracted price: **$70** (medium, unknown)
- priceSource: `v52-dominant-gate`
- gate distinct $-values: [70]
- gate matched token: `$70`
- gate ±40 char window:

  ```
  mond Beach Sunset night glow relaxation $70 People Prices for Sunday, May 10, 2026 
  ```
- all $-hits in page: ["$70"]

### 532164 — Tiki Bar Crawl by Water

- company: Six Fins Charter
- extracted price: **$1295** (medium, charter)
- priceSource: `v5.4 native`
- all $-hits in page: ["$1,295"]

### 532224 — Private Snorkel Adventure

- company: Six Fins Charter
- extracted price: **$1195** (medium, charter)
- priceSource: `v5.4 native`
- all $-hits in page: ["$1,195","$1,195"]

### 532226 — Private Secret Local Sandbars Escape

- company: Six Fins Charter
- extracted price: **$1195** (medium, charter)
- priceSource: `v5.4 native`
- all $-hits in page: ["$1,195"]

## 5. Sample 5 stays-hidden tours

### 358079 — 8 Hour Private Boat Tour

- outcome: low
- gate criterion failed: 2
- distinct $-values: [10,1299,2299,2999]
- all $-hits: ["$1,299","$2,299","$2,999","$10"]

### 666023 — Offshore/Deep Sea Charters

- outcome: low
- gate criterion failed: 2
- distinct $-values: [1100,1500,1800]
- all $-hits: ["$1,100","$1,500","$1,800"]

### 510265 — Salt Corporate Miami Ocean Adventures

- outcome: low
- gate criterion failed: 2
- distinct $-values: [2500,3900,6200]
- all $-hits: ["$2,500","$3,900","$6,200"]

### 434771 — Paddle Board Day Rentals

- outcome: low
- gate criterion failed: 2
- distinct $-values: [69,98,127,156,185,214,243,272,301]
- all $-hits: ["$69","$98","$127","$156","$185","$214","$243","$272","$301"]

### 226174 — Jupiter Clear Kayak Tour

- outcome: no-price

## 6. Out of scope for this run

- No edits to `tours-data.json`.
- No commits, no push, no deploy.
- `--live` mode not implemented yet — adopt USVI's `apply-v52-live.js` pattern when ready.

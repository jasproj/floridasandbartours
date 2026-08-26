# s50-fst-refresh — evidence bundle

Live FareHarbor refresh of the rendered-stale-with-ribbon population on floridasandbartours (WENG s48/s49 playbook, FST port). Branch `s50-fst-refresh` off origin/main `9ec228c`. One commit.

## Population (623 rows / 237 FareHarbor shortnames / 244 distinct `company` names)
Re-derived in-branch by `scripts/s50-fst-refresh.py` and asserted to 623/237 before any request:
- `CardFormat.drawable`: `status != 'inactive'` ∧ `!bookingDead` ∧ `!scope` (card-format.js:75 — the one pool predicate)
- visible ribbon: `Number(price) > 0` (card-format.js `priceText` — the only price gate on every grid)
- stale: newest evidence across `verifiedOn` / `verifiedDates` / `lastUpdated` / `statusCheckedAt` < 2026-08-01 (the 2026-07-24/25 `fh-api-expansion` + `fh-wholeboat-recovery` cohort, 361 rows, plus 262 legacy rows with no dated evidence at all)
- minus `excluded-ruled.json` (21 pks ruled in s38–s49: #138 card/catalogue sync, v52-dominant-gate, #149/#150 charter ladders)
- OUT: the 67 unrendered stale rows (42 inactive + 25 bookingDead) — no revenue surface.
- pk → item: every row's `bookingUrl` is `fareharbor.com/<shortname>/items/<pk>`; asserted `url pk == row pk` on all 623 (0 mismatches, 0 non-FareHarbor), so no positional resolution was needed.

`population.json` is the census-time pk list; the script's in-branch derivation must equal it (checked in verify).

## Instrument
`price-preview/per-item/v2?include_breakdown=yes`, ≤20 pks per request, 1 req/s, 4 dated requests per chunk (2026-08-31, 09-14, 09-28, 10-19). Item key is `id`. Absent from `items[]` = UNSAMPLED (never $0). Timeout/5xx → split chunk in half, retry once per half (bounded; every retry logged in `probe.json.retries`). Falsifiability control: an impossible shortname must not return 200 (it returned HTTP 400). Date-validity: a reading is date-valid when `availability.start_at[0:10]` equals the requested date; echo-dated ladders remain live evidence (D-638) and the caveat is stamped.

## Rules (apply)
| rule | effect |
|---|---|
| D-624 / D-625 | cheapest adult/base per-person tier anchors; child/infant/concession/add-on/gratuity/deposit tiers never anchor |
| D-637 / D-639 | "per additional person" is an add-on; the add-on sweep aborts the run only when the ANCHOR tier is add-on-shaped |
| D-640 | single-tier product anchors on its sole tier |
| D-614 | whole-boat / party-size / party-total ladders: the floor TOTAL anchors, never divided by headcount, unit `whole-boat` |
| s48-R1 | per-head rate ladder whose price FALLS as the band grows: largest band's per-person figure anchors |
| D-644 | deposit-only ladder → held |
| D-620 | live `details.currency` ≠ USD → held, true currency + amount stamped |
| UNSAMPLED / zero_price / PROBE_ERROR / never-only | held with reason |

**Suppression in this repo = `price: null`.** `CardFormat.priceText` returns null → the ribbon renders `Price at booking`, and `injectTourSchemas` never emitted a `price` in its Offer, so a held row loses its figure everywhere without any other flag. No renderer reads `priceConfidence`.

## Stamp — field mapping (WENG vocabulary → this repo)
| WENG (top-level) | FST | note |
|---|---|---|
| `priceSource` | `_unknownFields.priceSource` = `s50-fst-refresh` | |
| `priceEnrichmentAt` | `verifiedOn` (top-level and `_unknownFields`) + `lastUpdated` = `2026-08-25` | this repo has no `priceEnrichmentAt` |
| `priceBasis` | `_unknownFields.priceBasis` | rule, anchor tier, skipped tiers, readings, currency |
| `priceTiers` | `_unknownFields.priceTiers` | live majority ladder `[{name, note, price, minPartySize}]` |
| `priceUnit` | `_unknownFields.unit` ∈ `whole-boat` / `per-person` / `per-unit` / `per-vehicle` | CardFormat.unitPhrase's enumerated vocabulary, not a verbatim label; the label-substring fallback is untouched |
| `priceConfidence` high/low | `verified-adult` / `verified-whole-boat` / `verified-whole-unit` (+`-range` when the anchor varied across readings) / `held` | this repo's existing classes |
| `priceEnrichmentStatus` | `_unknownFields.priceHold` (held rows only) | UNSAMPLED / PROBE_ERROR / zero_price / deposit_only / never_only / non_usd_currency:XXX |
| `currency` (true currency on D-620) | `_unknownFields.liveCurrency` (+ `liveAmount`) | top-level `currency` stays USD |
| — | `_unknownFields.probeDates` / `probeSampled` / `probeDateValid` / `verifiedDates` (int, matches existing type) / `priceIncludesBookingFees` / `priceIncludesTaxes` / `minPartySize` / `minimumSpend` / `observedPriceRange` / `priceKind` | refreshed from the live reading; stale `observedPriceRange` / `minimumSpend` / `unit` / `priceBasisNote` / `singleObservation` / `priceVolatility` are dropped first |
| `priceLabel` | `"$N <unit phrase>"` (existing style, e.g. `$500 whole boat`) | held → `''` |

## Files
- `excluded-ruled.json` — 21 ruled pks left untouched
- `population.json` — 623 pks (census)
- `probe.json` / `probe.stdout` / `probe.stderr` — every request, retry, reading; `reconcile` block
- `apply-summary.json` — per-row old→new, disposition, tier classes, rule; `attempted` = `succeeded` = 623
- `render-harness.mjs` / `verify.json` — the real `card-format.js` run over before/after, delta decomposed; pool intact; 0 outside-population ribbon changes

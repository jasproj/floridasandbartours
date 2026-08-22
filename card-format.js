/*
 * card-format.js — shared card formatting for every tour grid on this property.
 *
 * WHY THIS FILE EXISTS
 * The JS grid had seven renderers (app.js plus six inline copies on the category
 * pages) and each one gated the price on `priceLabel === 'per adult'`. Exactly 17
 * of 3,536 pool rows carry that literal string, so 3,478 rows with a verified
 * price rendered "Check live price" instead. The price was read and discarded.
 * One implementation, loaded by all seven, is what stops that drifting again.
 *
 * The hand-authored blog card is the reference implementation:
 *     <div class="tags"><span class="tag">Kayak</span>...</div>
 *     <div class="price">$54 per single kayak</div>
 * Figure, then unit. A whole-boat rate must never read like a seat price.
 */
(function (global) {
  'use strict';

  /* ---- tag splitting -----------------------------------------------------
   * PORTED VERBATIM from wanderhawaii scripts/normalize-tags.mjs. Do not
   * reimplement: a naive split('-') breaks E-Bike and Self-Guided Tour, which
   * is exactly what HYPHENATED_TOKENS exists to prevent.
   */
  var HYPHENATED_TOKENS = ['E-Bike', 'Self-Guided Tour'];

  function isCompound(v) { return typeof v === 'string' && v.indexOf('-') !== -1; }

  function splitTagValue(value) {
    if (!isCompound(value)) return [value];
    var parts = value.split('-').map(function (p) { return p.trim(); }).filter(Boolean);
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      var pair = parts[i] + '-' + (parts[i + 1] || '');
      var known = HYPHENATED_TOKENS.some(function (t) { return t.toLowerCase() === pair.toLowerCase(); });
      if (i + 1 < parts.length && known) { out.push(pair); i++; }
      else out.push(parts[i]);
    }
    return out;
  }

  /** Split every tag on a row, de-duplicated, order preserved. */
  function displayTags(tour, limit) {
    var out = [];
    var tags = (tour && tour.tags) || [];
    for (var i = 0; i < tags.length; i++) {
      var parts = splitTagValue(tags[i]);
      for (var j = 0; j < parts.length; j++) {
        if (parts[j] && out.indexOf(parts[j]) === -1) out.push(parts[j]);
      }
    }
    return typeof limit === 'number' ? out.slice(0, limit) : out;
  }

  /* ---- scope --------------------------------------------------------------
   * Some catalogue rows are real, bookable products that are simply not what
   * this site sells: firearms ranges, escape rooms, culinary walking tours,
   * a railroad museum, exotic-car rentals, villa lets. They are kept in the
   * catalogue -- nothing is deleted -- and marked with a `scope` value that
   * holds them off every rendered surface.
   *
   * Any truthy `scope` excludes. Adding a new scope value therefore needs no
   * change here, which is the point: one predicate, seven grids.
   *
   * NOT the same thing as `status: "inactive"`. That field is owned by the
   * Auto-Rot-Cleanup Agent and means the product DIED; a run that finds the
   * product alive again may clear it. Scope means we do not sell this, which
   * is not a fact about the product's lifecycle and must not be undone by a
   * liveness check.
   */
  function isInScope(tour) {
    return !(tour && tour.scope);
  }

  /** The rows a grid may draw from: live per app.js, and in scope. */
  function drawable(tours) {
    return (tours || []).filter(function (t) {
      return t && t.status !== 'inactive' && !t.bookingDead && isInScope(t);
    });
  }

  /* ---- region -------------------------------------------------------------
   * ONE region lookup for the whole property. app.js and the six category
   * pages all matched regions themselves before this; the category copies
   * tested `island.includes('south florida')` against values shaped
   * `united states/florida/<municipality>` and so matched nothing at all,
   * while app.js kept a keyword list that covered 2,376 of 3,536 rows and
   * was never extended when the pool grew to 3,536. Same lesson as
   * HYPHENATED_TOKENS: one definition, imported, never re-implemented.
   *
   * Keyed on the MUNICIPALITY — the last `/` segment of `location`, lowercased,
   * which is exactly what `island` already holds. Substring keywords are not
   * used: they made 'st. pete' match both St. Petersburg and St. Pete Beach by
   * luck rather than by intent, and silently dropped every municipality nobody
   * had thought to list.
   *
   * The lists were derived from the catalogue, not written from memory.
   * `scripts/check-region-coverage.mjs` re-derives them and fails when a
   * municipality appears in the data that is not mapped here — so the next
   * stocking run reports the gap instead of silently dropping rows.
   */
  var FLORIDA_REGIONS = {
    'south florida': [
    'alva', 'big pine key', 'boca grande', 'boca raton', 'bokeelia', 'bonita springs',
    'canal point', 'cape coral', 'captiva', 'captiva island', 'chokoloskee', 'coconut grove',
    'dania beach', 'delray beach', 'doral', 'everglades city', 'fellsmere', 'fort lauderdale',
    'fort myers', 'fort myers beach', 'fort pierce', 'goodland', 'hollywood', 'homestead',
    'islamorada', 'jupiter', 'key biscayne', 'key colony beach', 'key largo', 'key west',
    'lake park', 'lighthouse point', 'loxahatchee', 'marathon', 'marco island', 'matlacha',
    'miami', 'miami beach', 'miami river', 'miami shores', 'naples', 'naples fl',
    'north fort myers', 'north miami', 'north miami beach', 'ochopee', 'palm beach',
    'palm beach shores', 'palm city', 'parkland', 'pompano beach', 'port charlotte',
    'riviera beach', 'sanibel', 'sanibel island', 'sebastian', 'st james city', 'stock island',
    'stuart', 'summerland key', 'tavernier', 'vero beach', 'west palm beach', 'weston',
    ],
    'central florida': [
    'anna maria', 'apollo beach', 'apopka', 'belle isle', 'belleair bluffs', 'beverly hills',
    'bradenton', 'bradenton beach', 'brooksville', 'cape canaveral', 'casselberry', 'chuluota',
    'citrus springs', 'clearwater', 'clearwater beach', 'clermont', 'cocoa', 'cocoa beach',
    'cortez', 'crystal river', 'dade city', 'dunedin', 'dunnellon', 'englewood', 'eustis',
    'grant-valkaria', 'gulfport', 'hernando beach', 'holmes beach', 'homosassa',
    'homosassa springs', 'hudson', 'indian harbour beach', 'indian rocks beach', 'inglis',
    'inverness', 'kissimmee', 'lake panasoffkee', 'lakewood ranch', 'largo', 'lecanto',
    'leesburg', 'lido key- ted sperling nature park', 'longboat key', 'longwood', 'lutz',
    'madeira beach', 'melbourne', 'melbourne beach', 'merritt island', 'mims', 'mount dora',
    'myakka city', 'nokomis', 'north port', 'north redington beach', 'ocala', 'orlando',
    'osprey', 'oviedo', 'palm bay', 'palm harbor', 'palmetto', 'parrish', 'plant city',
    'port canaveral', 'port richey', 'pt canaveral', 'riverview', 'ruskin', 'safety harbor',
    'sanford', 'sarasota', 'satellite beach', 'sebring', 'seminole', 'siesta key',
    'siesta key - turtle beach', 'silver springs', 'sorrento', 'south pasadena', 'spring hill',
    'st petersburg', 'st. cloud', 'st. pete beach', 'st. petersburg', 'tampa', 'tarpon springs',
    'tierra verde', 'titusville', 'town \'n\' country', 'treasure island', 'venice',
    'west bradenton', 'williston', 'wimauma', 'winter haven', 'winter park', 'yankeetown',
    ],
    'north florida': [
    'baker', 'branford', 'crestview', 'daytona beach', 'de leon springs', 'deland', 'deltona',
    'destin', 'fernandina beach', 'fort walton', 'fort walton beach', 'fort white',
    'ft. walton beach', 'gulf breeze', 'hastings', 'high springs', 'holt', 'jacksonville',
    'jacksonville beach', 'live oak', 'marianna', 'mary ester', 'mary esther', 'mayport',
    'milton', 'miramar beach', 'navarre', 'navarre beach', 'new smyrna beach', 'niceville',
    'oak hill', 'okaloosa island', 'orange city', 'pace', 'palatka', 'palm valley',
    'panama city', 'panama city beach', 'pensacola', 'pensacola beach', 'perdido key',
    'santa rosa beach', 'shalimar', 'st augustine', 'st. augustine', 'wakulla springs',
    ]
  };

  var MUNICIPALITY_REGION = (function () {
    var out = {};
    for (var region in FLORIDA_REGIONS) {
      if (!Object.prototype.hasOwnProperty.call(FLORIDA_REGIONS, region)) continue;
      var list = FLORIDA_REGIONS[region];
      for (var i = 0; i < list.length; i++) out[list[i]] = region;
    }
    return out;
  })();

  /** The municipality a row is filed under: last path segment, lowercased. */
  function municipalityOf(tour) {
    var loc = (tour && (tour.location || tour.island)) || '';
    var parts = String(loc).split('/');
    return parts[parts.length - 1].trim().toLowerCase();
  }

  /**
   * The region a row belongs to, or null.
   *
   * 35 rows are filed under a municipality that is not in Florida at all —
   * Omaha, Chicago, New York — because `locationSource` was the operator's
   * billing address. Those rows carry the real municipality in
   * `_unknownFields.locationDiffersFromExport`, so it is consulted when, and
   * only when, the primary municipality is unknown. It cannot reclassify a
   * row that already resolves.
   */
  function regionOf(tour) {
    var r = MUNICIPALITY_REGION[municipalityOf(tour)];
    if (r) return r;
    var uf = (tour && tour._unknownFields) || {};
    var alt = uf.locationDiffersFromExport;
    if (alt) {
      var parts = String(alt).split('/');
      r = MUNICIPALITY_REGION[parts[parts.length - 1].trim().toLowerCase()];
      if (r) return r;
    }
    return null;
  }

  /** True when `region` is falsy (no filter) or the row is in that region. */
  function matchesRegion(tour, region) {
    if (!region) return true;
    return regionOf(tour) === String(region).trim().toLowerCase();
  }

  /* ---- price -------------------------------------------------------------- */

  function money(n) {
    if (!isFinite(n)) return '';
    var whole = Math.abs(n - Math.round(n)) < 0.005;
    return '$' + (whole ? Math.round(n).toLocaleString('en-US')
                        : Number(n).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ','));
  }

  /* The unit is what stops an $895 whole-boat charter reading like a $45 seat.
     Prefer the recorded unit; fall back to what the stored label says. */
  function unitPhrase(tour) {
    var uf = (tour && tour._unknownFields) || {};
    var unit = uf.unit;
    if (!unit) {
      var lbl = String((tour && tour.priceLabel) || '').toLowerCase();
      if (lbl.indexOf('whole boat') !== -1 || lbl.indexOf('charter') !== -1) unit = 'whole-boat';
      else if (lbl.indexOf('per unit') !== -1) unit = 'per-unit';
      else if (lbl.indexOf('per craft') !== -1) unit = 'per-vehicle';
      else if (lbl.indexOf('per person') !== -1 || lbl.indexOf('per adult') !== -1) unit = 'per-person';
    }
    if (unit === 'whole-boat') {
      var note = String(uf.customerTypeVerified || '') + ' ' + String(uf.customerTypeNote || '');
      var cap = note.match(/(includes\s+\d+\s*(?:people|guests|passengers)|up to\s+\d+\s*(?:people|guests|passengers))/i);
      return 'whole boat' + (cap ? ', ' + cap[1].trim().toLowerCase() : '');
    }
    if (unit === 'per-unit') return 'per unit';
    if (unit === 'per-vehicle') return 'per craft';
    if (unit === 'per-person') return 'per person';
    return '';
  }

  /**
   * The text for the price ribbon, or null when the row has no usable price.
   * Where verification produced a range, the range is shown — publishing only
   * the low end of a $650–$900 charter understates it.
   */
  function priceText(tour) {
    if (!tour) return null;
    var n = Number(tour.price);
    if (!isFinite(n) || n <= 0) return null;
    var uf = tour._unknownFields || {};
    var r = uf.observedPriceRange;
    var figure;
    if (Array.isArray(r) && r.length === 2 && isFinite(Number(r[0])) && Number(r[1]) > Number(r[0])) {
      figure = money(Number(r[0])) + '–' + money(Number(r[1]));
    } else {
      figure = money(n);
    }
    var unit = unitPhrase(tour);
    return unit ? figure + ' ' + unit : figure;
  }

  /** Minimum-spend note for tiers that cannot be booked singly. */
  function minSpendNote(tour) {
    var uf = (tour && tour._unknownFields) || {};
    var min = Number(uf.minPartySize);
    var spend = Number(uf.minimumSpend);
    if (!isFinite(min) || min <= 1) return '';
    return isFinite(spend) ? 'Minimum ' + min + ', from ' + money(spend) : 'Minimum ' + min;
  }

  /**
   * The honest fallback. It says what is true — that the price is set by the
   * operator at booking — rather than implying we have one and are hiding it.
   */
  var NO_PRICE_TEXT = 'Price at booking';

  function priceRibbonHTML(tour) {
    var txt = priceText(tour);
    if (!txt) return '<span class="price-ribbon-fallback">' + NO_PRICE_TEXT + '</span>';
    var note = minSpendNote(tour);
    var title = note ? ' title="' + note.replace(/"/g, '&quot;') + '"' : '';
    return '<span class="price-ribbon"' + title + '>' + txt + '</span>';
  }

  /** The row's own description wins; the caller supplies the last-resort text. */
  function description(tour, fallbackFn) {
    var d = tour && tour.description;
    if (typeof d === 'string' && d.trim() !== '') return d.trim();
    return typeof fallbackFn === 'function' ? fallbackFn(tour) : '';
  }

  global.CardFormat = {
    HYPHENATED_TOKENS: HYPHENATED_TOKENS,
    isCompound: isCompound,
    splitTagValue: splitTagValue,
    displayTags: displayTags,
    priceText: priceText,
    priceRibbonHTML: priceRibbonHTML,
    minSpendNote: minSpendNote,
    description: description,
    NO_PRICE_TEXT: NO_PRICE_TEXT,
    FLORIDA_REGIONS: FLORIDA_REGIONS,
    municipalityOf: municipalityOf,
    regionOf: regionOf,
    matchesRegion: matchesRegion,
    isInScope: isInScope,
    drawable: drawable
  };
})(typeof window !== 'undefined' ? window : this);

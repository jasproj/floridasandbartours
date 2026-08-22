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
    NO_PRICE_TEXT: NO_PRICE_TEXT
  };
})(typeof window !== 'undefined' ? window : this);

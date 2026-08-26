#!/usr/bin/env node
// Render verify: run the REAL CardFormat (card-format.js, unmodified) over the population before and after,
// and decompose the ribbon delta. usage: node scripts/evidence/s50-fst-refresh/render-harness.mjs <before.json> <after.json> <pop.json>
import fs from 'node:fs'; import vm from 'node:vm';
const [before, after, popFile] = process.argv.slice(2);
const ctx = {}; vm.createContext(ctx); vm.runInContext(fs.readFileSync('card-format.js', 'utf8'), ctx);
const CF = ctx.CardFormat;
const load = f => new Map(JSON.parse(fs.readFileSync(f, 'utf8')).tours.map(t => [String(t.pk), t]));
const B = load(before), A = load(after); const pop = JSON.parse(fs.readFileSync(popFile, 'utf8')).map(String);
const ribbon = t => t ? CF.priceRibbonHTML(t) : null; const text = t => t ? CF.priceText(t) : null;
const fig = s => s ? Number((s.match(/\$([\d,]+(?:\.\d+)?)/) || [])[1]?.replace(/,/g, '')) : null;
const unit = s => s ? (s.replace(/^\$[\d,.]+(–\$[\d,.]+)?\s*/, '') || '(no unit)') : null;
const out = { population: pop.length, drawableBefore: 0, drawableAfter: 0, classes: {}, unitChanges: {}, rows: [] };
const bump = k => { out.classes[k] = (out.classes[k] || 0) + 1; };
for (const pk of pop) {
  const b = B.get(pk), a = A.get(pk); if (!b || !a) { bump('MISSING'); continue; }
  out.drawableBefore += CF.drawable([b]).length; out.drawableAfter += CF.drawable([a]).length;
  const tb = text(b), ta = text(a); let cls;
  if (tb && !ta) cls = 'suppressed→Price at booking'; else if (!tb && ta) cls = 'newly priced';
  else if (tb === ta) cls = 'ribbon identical'; else if (fig(tb) === fig(ta)) cls = 'same figure, unit phrase changed';
  else cls = fig(ta) > fig(tb) ? 'repriced up' : 'repriced down';
  bump(cls); const uk = `${unit(tb)} → ${unit(ta)}`; if (unit(tb) !== unit(ta)) out.unitChanges[uk] = (out.unitChanges[uk] || 0) + 1;
  out.rows.push({ pk, name: a.name, before: tb, after: ta, cls, ribbonBefore: ribbon(b), ribbonAfter: ribbon(a) });
}
// every drawable-before row must still be drawable-after (this PR touches price, never pool membership)
out.poolIntact = out.drawableBefore === out.drawableAfter && out.drawableAfter === pop.length;
// outside-population rows must render byte-identically
let outsideChanged = 0; for (const [pk, b] of B) if (!pop.includes(pk)) { const a = A.get(pk); if (!a || ribbon(a) !== ribbon(b)) outsideChanged++; }
out.outsidePopulationRibbonChanged = outsideChanged;
fs.writeFileSync('scripts/evidence/s50-fst-refresh/verify.json', JSON.stringify(out, null, 1) + '\n');
console.log(JSON.stringify({ population: out.population, poolIntact: out.poolIntact, outsidePopulationRibbonChanged: outsideChanged, classes: out.classes, unitChanges: out.unitChanges }, null, 1));

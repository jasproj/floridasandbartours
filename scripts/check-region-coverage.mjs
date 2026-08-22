#!/usr/bin/env node
/*
 * check-region-coverage.mjs — does every municipality in the catalogue map to a region?
 *
 * WHY THIS EXISTS
 * The region filter did not break because the lookup was wrong when it was
 * written. It broke because the pool grew from 844 rows to 3,536 and nobody
 * extended the lookup, so 1,160 rows in 157 municipalities silently stopped
 * matching any region. Nothing reported it. This does.
 *
 * Run after any stocking run:
 *     node scripts/check-region-coverage.mjs          # report
 *     node scripts/check-region-coverage.mjs --check  # exit 1 if anything is unmapped
 *
 * It reads the SHARED lookup out of card-format.js rather than keeping a second
 * copy of the region lists, so it cannot drift from what the site actually uses.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const strict = process.argv.includes('--check');

// Load the real shared module, exactly as a browser would.
const shim = { CardFormat: null };
new Function('window', readFileSync(join(ROOT, 'card-format.js'), 'utf8'))(shim);
const CF = shim.CardFormat;
if (!CF || typeof CF.regionOf !== 'function') {
  console.error('FAIL: card-format.js did not expose CardFormat.regionOf');
  process.exit(2);
}

const raw = JSON.parse(readFileSync(join(ROOT, 'tours-data.json'), 'utf8'));
const rows = Array.isArray(raw) ? raw : raw.tours;
// Same predicate as app.js:144 — only rows that can actually reach a grid matter.
const pool = rows.filter(t => t.status !== 'inactive' && !t.bookingDead);

const unmapped = new Map();
const byRegion = Object.create(null);
for (const t of pool) {
  const region = CF.regionOf(t);
  if (region) { byRegion[region] = (byRegion[region] || 0) + 1; continue; }
  const m = CF.municipalityOf(t);
  if (!unmapped.has(m)) unmapped.set(m, { rows: 0, examples: [] });
  const e = unmapped.get(m);
  e.rows++;
  if (e.examples.length < 3) e.examples.push(`${t.company} — ${t.name}`);
}

const mapped = Object.values(CF.FLORIDA_REGIONS).reduce((a, b) => a + b.length, 0);
const unresolved = [...unmapped.values()].reduce((a, e) => a + e.rows, 0);

console.log(`pool rows              ${pool.length}`);
console.log(`municipalities mapped  ${mapped}`);
for (const r of Object.keys(CF.FLORIDA_REGIONS)) {
  console.log(`  ${r.padEnd(16)} ${String(byRegion[r] || 0).padStart(5)} rows`);
}
console.log(`rows with NO region    ${unresolved}`);

if (unmapped.size) {
  console.log(`\n${unmapped.size} municipalit${unmapped.size === 1 ? 'y' : 'ies'} not mapped in card-format.js FLORIDA_REGIONS:`);
  for (const [m, e] of [...unmapped].sort((a, b) => b[1].rows - a[1].rows)) {
    console.log(`  ${String(e.rows).padStart(4)}  ${m}`);
    for (const x of e.examples) console.log(`        ${x}`);
  }
  console.log('\nAdd each to the right region list in card-format.js, or — if the row is');
  console.log('filed under an operator billing address rather than where it operates —');
  console.log('confirm _unknownFields.locationDiffersFromExport carries the real one.');
  if (strict) process.exit(1);
} else {
  console.log('\nOK: every pool row resolves to a region.');
}

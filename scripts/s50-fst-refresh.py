#!/usr/bin/env python3
"""s50-fst-refresh — live FareHarbor refresh of the rendered-stale-with-ribbon population (WENG s48/s49 playbook, FST port).

POPULATION (re-derived in-branch; must equal 623 rows / 237 FareHarbor shortnames (244 distinct company names))
  CardFormat.drawable  : status != 'inactive' AND NOT bookingDead AND NOT scope
  visible ribbon       : Number(price) > 0            (card-format.js priceText — the only gate)
  stale                : newest evidence < 2026-08-01 (verifiedOn / verifiedDates / lastUpdated / statusCheckedAt)
  MINUS                : evidence/excluded-ruled.json (21 pks ruled in s38–s49: #138 card/catalogue sync, v52 gate, #149/#150 charters)
  pk -> item           : bookingUrl fareharbor.com/<shortname>/items/<pk>; asserted pk == row pk on every row.

ENDPOINT / INSTRUMENT (D-606 / D-613 lineage; probe-charter-ladders.py rules carried)
  price-preview/per-item/v2, include_breakdown=yes, <=20 pks per request, 1 req/s, 4 dated requests.
  Item key is `id` (never `pk`). Absent from items[] = UNSAMPLED, never $0. $0 tiers are not fares (D-575).
  start_at echo: a reading is date-valid when start_at[0:10] == requested date; echo-dated ladders are still
  live evidence (D-638) and are recorded as a caveat. Falsifiability: an impossible shortname must not 200.
  Timeout / 5xx: split the chunk in half and retry once per half (bounded, logged).

ANCHOR RULES (apply mode)
  D-624   cheapest ADULT/BASE per-person tier anchors "From"; child/infant/concession/add-on/gratuity never do.
  D-625   same-customer-type ladders split by logistics are one product — cheapest base wins.
  D-637   smallest bookable unit anchors; "per additional person" is an add-on and never anchors.
  D-639   add-on abort fires only when the ANCHOR tier itself is add-on-shaped (label or note).
  D-640   a single-tier product anchors on its sole tier.
  D-614   whole-boat / party-size / party-total ladders: the FLOOR total anchors, unit whole-boat (never divided by headcount).
  s48-R1  per-head rate ladder whose price FALLS as the band grows: largest band's per-person figure anchors.
  D-644   a deposit tier is never a price — deposit-only ladders are held.
  D-620   live details.currency != USD: held, true currency + amount stamped.
  UNSAMPLED / zero_price / probe_error: held with reason.
  HELD in this repo == price null -> CardFormat renders "Price at booking" (the honest state). Nothing else gates.

STAMPS (this repo's vocabulary, complete and dated)
  _unknownFields.priceSource = "s50-fst-refresh"; _unknownFields.priceBasis; _unknownFields.priceTiers (live majority ladder);
  _unknownFields.unit (whole-boat | per-person | per-unit | per-vehicle — CardFormat.unitPhrase's enumerated vocabulary) where derivable;
  _unknownFields.minPartySize from the anchor tier; _unknownFields.liveCurrency; top-level verifiedOn + lastUpdated = 2026-08-25.
  Field mapping vs the WENG stamp is in evidence/README.md.

usage: python3 scripts/s50-fst-refresh.py probe|apply [--dry-run]
"""
import collections, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

FILE = 'tours-data.json'
EV = 'scripts/evidence/s50-fst-refresh'
SOURCE = 's50-fst-refresh'
STAMP_DAY = '2026-08-25'
STALE_BEFORE = '2026-08-01'
DATES = ['2026-08-31', '2026-09-14', '2026-09-28', '2026-10-19']
BATCH, RATE_S, TIMEOUT_S = 20, 1.0, 25
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
IMPOSSIBLE_SN = 'definitely-not-a-real-fh-shortname-zzz'
API = 'https://fareharbor.com/api/embed/{sn}/price-preview/per-item/v2/?item_pks={pks}&include_breakdown=yes&date={date}'
FH_RE = re.compile(r'fareharbor\.com/(?:embeds/book/)?([^/?#]+)/items/(\d+)')

def u(cents): return round(cents / 100.0, 2)
def uf(t): return t.get('_unknownFields') or {}

# ---------------- population ----------------
def newest_evidence(t):
    c = []
    x = uf(t)
    for k in ('verifiedOn', 'bookableSampleDate'):
        v = x.get(k)
        if isinstance(v, str) and v[:4] == '2026': c.append(v[:10])
    vd = x.get('verifiedDates')
    if isinstance(vd, list): c += [d[:10] for d in vd if isinstance(d, str) and d[:4] == '2026']
    for k in ('lastUpdated', 'statusCheckedAt'):
        v = t.get(k)
        if isinstance(v, str) and v[:4] == '2026': c.append(v[:10])
    return max(c) if c else ''

def drawable(t): return t.get('status') != 'inactive' and not t.get('bookingDead') and not t.get('scope')
def visible(t):
    try: return float(t.get('price')) > 0
    except (TypeError, ValueError): return False

def load():
    raw = open(FILE, encoding='utf-8').read()
    doc = json.loads(raw)
    if json.dumps(doc, indent=2, ensure_ascii=False) != raw:
        sys.exit('ABORT: no byte round-trip (D-599)')
    excluded = set(json.load(open(f'{EV}/excluded-ruled.json')))
    pop = [t for t in doc['tours'] if drawable(t) and visible(t) and newest_evidence(t) < STALE_BEFORE and str(t['pk']) not in excluded]
    for t in pop:
        m = FH_RE.search(t.get('bookingUrl') or '')
        if not m or m.group(2) != str(t['pk']):
            sys.exit(f'ABORT: bookingUrl pk mismatch / non-FareHarbor on {t["pk"]}')
        t['_sn'] = m.group(1)
    sns = {t['_sn'] for t in pop}
    print(f'population {len(pop)} rows / {len(sns)} shortnames (excluded ruled {len(excluded)})', file=sys.stderr)
    if len(pop) != 623 or len(sns) != 237:
        sys.exit(f'ABORT: population drift — expected 623/237, got {len(pop)}/{len(sns)}')
    return doc, pop

# ---------------- probe ----------------
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            if r.status != 200: return {'err': f'HTTP {r.status}'}
            return {'j': json.loads(r.read().decode('utf-8', 'replace'))}
    except urllib.error.HTTPError as e: return {'err': f'HTTP {e.code}'}
    except Exception as e: return {'err': 'timeout' if 'timed out' in str(e) else str(e)[:120]}

def probe():
    doc, pop = load()
    c = get(API.format(sn=IMPOSSIBLE_SN, pks='1', date=DATES[0])); time.sleep(RATE_S)
    control = {'shortname': IMPOSSIBLE_SN, 'result': c.get('err') or 'HTTP 200', 'falsifiable': 'j' not in c}
    print(f'[control] {control}', file=sys.stderr)
    if not control['falsifiable']: sys.exit('FATAL: impossible shortname returned 200 — instrument not falsifiable')
    by_sn = collections.OrderedDict()
    for t in pop: by_sn.setdefault(t['_sn'], []).append(t['pk'])
    out = {'startedAt': datetime.now(timezone.utc).isoformat(), 'dates': DATES, 'population': len(pop), 'shortnames': len(by_sn),
           'control': control, 'requests': 0, 'retries': [], 'perPk': {str(t['pk']): {'sn': t['_sn'], 'probes': []} for t in pop}}
    def run(sn, pks, date, depth):
        out['requests'] += 1
        x = get(API.format(sn=sn, pks=','.join(map(str, pks)), date=date)); time.sleep(RATE_S)
        if 'err' in x and re.search(r'timeout|HTTP 5', x['err']) and len(pks) > 1 and depth < 2:
            out['retries'].append({'sn': sn, 'date': date, 'size': len(pks), 'err': x['err'], 'split': True})
            h = (len(pks) + 1) // 2; time.sleep(2)
            run(sn, pks[:h], date, depth + 1); run(sn, pks[h:], date, depth + 1); return
        j = x.get('j') or {}
        items = {int(it.get('id', -1)): it for it in (j.get('items') or [])}   # key is `id`, never `pk`
        det = j.get('details') or {}
        for pk in pks:
            it = items.get(pk); p = {'date': date, 'error': x.get('err')}
            if 'err' not in x:
                p.update(absent=it is None, liveCurrency=det.get('currency'), includeFees=det.get('prices_include_booking_fees'), includeTaxes=det.get('prices_include_taxes'))
            if it:
                sa = (it.get('availability') or {}).get('start_at'); p['start_at'] = sa; p['dateValid'] = bool(sa) and sa[:10] == date
                cts = ((it.get('price') or {}).get('breakdown') or {}).get('customer_types') or []
                p['tiers'] = [{'id': ct.get('id'), 'singular': ct.get('singular'), 'plural': ct.get('plural'), 'note': ct.get('note'),
                               'priceCents': ct.get('price'), 'min': ct.get('min_party_size')} for ct in cts]
                p['low'] = (it.get('price') or {}).get('low'); p['zeroOnly'] = not any((ct.get('price') or 0) > 0 for ct in cts)
            out['perPk'][str(pk)]['probes'].append(p)
    n = 0
    for sn, pks in by_sn.items():
        for i in range(0, len(pks), BATCH):
            for date in DATES: run(sn, pks[i:i + BATCH], date, 0)
        n += 1
        if n % 10 == 0: print(f'{n}/{len(by_sn)} operators, {out["requests"]} req', file=sys.stderr)
        json.dump(out, open(f'{EV}/probe.json', 'w'))
    out['finishedAt'] = datetime.now(timezone.utc).isoformat()
    bad = [k for k, v in out['perPk'].items() if len(v['probes']) != len(DATES)]
    out['reconcile'] = {'population': len(pop), 'pksWithFullProbeSet': len(pop) - len(bad), 'incomplete': bad}
    json.dump(out, open(f'{EV}/probe.json', 'w'))
    print(json.dumps({'requests': out['requests'], 'retries': len(out['retries']), 'reconcile': out['reconcile']}))

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'probe': probe()
    elif mode == 'apply':
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from s50_fst_apply import apply; apply(load, '--dry-run' in sys.argv)
    else: sys.exit('usage: probe|apply [--dry-run]')

#!/usr/bin/env python3
"""s51-fst-held-ingest — ingest the 56 ingest_as_normal_row pks from the retired
held-tours-needs-operator-key.json triage (scratchpad/s51-fst-62-triage.json, #154).

These 56 pks are NOT currently in tours-data.json (they never made it past the
2026-07-24 held-file parking). This adds new rows, not a refresh.

ANCHOR ENGINE: imports classify() / unit_for() / CONF / PHRASE / u() / money()
verbatim from scripts/s50_fst_apply.py -- the same standing tier-anchor family
(D-624/D-625/D-637/D-639/D-640/D-614/s48-R1/D-644/D-620) used on every other
row in this repo. No new pricing logic is introduced here.

INSTRUMENT: price-preview/per-item/v2, include_breakdown=yes, <=20 pks/request,
1 req/s, falsifiability control, timeout/5xx retry-by-split (probe-charter-
ladders.py / s50-fst-refresh.py lineage). Item key is `id`, never `pk`.

DATES: 4 dates spanning 60 days (2026-08-27 / 09-16 / 10-06 / 10-26) for every
pk in this batch -- this satisfies "sweep 4 dates across 60 days before
declaring UNSAMPLED" for the 6 rows that came back UNSAMPLED on the narrower
recon probe, and is applied uniformly to all 56 for one clean evidence set.

HOLD RULE: a pk absent from items[] on all 4 dates is UNSAMPLED. Per
instruction, low never releases -- an UNSAMPLED row is still added (it passed
scope triage) but with price null / priceConfidence 'held', never a
priceBoundsCents.low guess.

STAMPS: _unknownFields.priceSource = 's51-fst-held-ingest'; top-level
verifiedOn + lastUpdated = 2026-08-26; _unknownFields.verifiedOn = 2026-08-26;
_unknownFields.verifiedDates = sampled count (the same 4-field dated stamp
convention s50 used).

usage: python3 scripts/s51-fst-held-ingest.py probe|apply [--dry-run]
"""
import collections, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s50_fst_apply import classify, unit_for, u, money, CONF, PHRASE, headcount, ADDON, NOTE_NEVER, DEPOSIT

# Manual audit (2026-08-26): every one of the 49 engine-picked anchors from the
# first apply pass was read against its full tier list by hand. 8 anchors were
# provably wrong -- the engine picked a child/non-participant/staff/promo tier
# because its label didn't match the existing NEVER/ACCESSORY/rider-exclusion
# vocabulary (documented per-pk below). These are narrow, cited corrections to
# the ANCHOR SELECTION only -- classify()/unit_for() themselves are untouched.
# 2 more (670424's sibling items 670442/670641) turned out to be the same
# structurally-ambiguous lettered/voucher-code mess as 670424 (already ruled
# genuinely_blocked) once the full tier list is read; they are held here, not
# ingested with a price, and should move to the genuinely_blocked pile.
MANUAL_ANCHOR = {
    31348: ('Participant', 'engine picked "Ride Only Passenger" $50.95 (a non-swimming ride-along '
            'variant) because it matched BASE_HEAD, not the rider/ride-along exclusion (which only '
            'fullmatches "rider"/"ride-along"/"passenger only"/"non-diver"); the true participant tier is "Participant" $75.95'),
    128628: ('Adult Snorkeler', 'engine picked "Adult Rider" $50 (boat-ride-only, no snorkeling) for the same '
             'reason as 31348; the true tier is "Adult Snorkeler" $60'),
    647364: ('Guest', 'engine picked "Guest (Ages 0-10)" $28 -- a child fare that reads as a base tier because '
              'NEVER/AGE_RANGE never fire on "(Ages 0-10)" without a "years"-suffixed range; the adult tier is "Guest" $42'),
    651796: ('Adult', 'engine picked "Viewer" $100 ("take a ride without taking a dip") -- a non-diver observer '
             'tier not in the NEVER vocabulary; the true participant tier is "Adult" $225'),
    655197: ('Adult Ticket', 'engine picked "First Responder Ticket" $60 -- a concession class absent from the '
             'NEVER vocabulary; the adult tier is "Adult Ticket" $65'),
    669055: ('Adult', 'engine picked "AB Adult (50% Off)" $21 -- a promo-discount variant of Adult, not caught by '
              'NEVER (which matches the word "discount", not "(50% Off)"); the list-price adult tier is "Adult" $41.99'),
    706306: ('Person', 'engine picked "Little One" (Ages 0-3) $5 -- an infant ticket under a euphemistic label '
             'absent from the NEVER vocabulary (infant/toddler/baby); the adult tier is "Person" $25'),
    626321: ('Person (without snorkel gear)', 'engine excluded both "Person (with/without snorkel gear)" tiers via '
             'the ACCESSORY regex matching the phrase "snorkel gear" in the tier label itself (a false positive -- '
             'these ARE the base per-person tour tiers, gear-inclusive vs BYO, not accessory upsells), leaving only '
             'the $125 private-tour upsell to float to the top; the true base tier is "Person (without snorkel gear)" $75'),
}
MANUAL_HOLD = {
    670442: 'genuinely_blocked, same shape as sibling 670424: 14 base-classed tiers are parallel lettered/coded '
            'Adult variants (Cruise Rate B/C/D/G/FTC, Tour Guide A-G) ranging $9-$87 with no canonical rate; the '
            'engine floors on "AB Tour Guide (D) Adult" $9, an internal guide rate, not a public price -- moved to '
            'genuinely_blocked, not ingested with a price',
    670641: 'genuinely_blocked: party-size private-tour tiers ("AB Private Tour Party 1-4" $449) are mixed with '
            'unrelated "Animal Encounter" add-on tiers and GRPN/VPAK/Groupon voucher-redemption codes in the same '
            'ladder; the engine floors on "Animal Encounter $45", an unrelated add-on, not the private tour itself -- '
            'moved to genuinely_blocked, not ingested with a price',
}

FILE = 'tours-data.json'
TRIAGE = 'scratchpad/s51-fst-62-triage.json'
EV = 'scripts/evidence/s51-fst-held-ingest'
SOURCE = 's51-fst-held-ingest'
STAMP_DAY = '2026-08-26'
SITE_CUR = 'USD'
DATES = ['2026-08-27', '2026-09-16', '2026-10-06', '2026-10-26']   # 4 dates / 60 days
BATCH, RATE_S, TIMEOUT_S = 20, 1.0, 25
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
IMPOSSIBLE_SN = 'definitely-not-a-real-fh-shortname-zzz'
API = 'https://fareharbor.com/api/embed/{sn}/price-preview/per-item/v2/?item_pks={pks}&include_breakdown=yes&date={date}'


def load_population():
    triage = json.load(open(TRIAGE))
    rows = triage['piles']['ingest_as_normal_row']['rows']
    src = {h['pk']: h for h in json.load(open('/tmp/ingest56_source.json'))}
    pop = []
    for r in rows:
        h = src[r['pk']]
        pop.append({'pk': h['pk'], 'sn': h['shortname'], 'name': h['name'], 'city': h['city'],
                    'tags': h.get('tags', ''), 'qualityScore': h.get('qualityScore'),
                    'bookingUrl': h['bookingUrl'], 'company': h.get('liveness', {}).get('company_name', '')})
    if len(pop) != 56:
        sys.exit(f'ABORT: population drift -- expected 56, got {len(pop)}')
    return pop


# ---------------- probe ----------------
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            if r.status != 200:
                return {'err': f'HTTP {r.status}'}
            return {'j': json.loads(r.read().decode('utf-8', 'replace'))}
    except urllib.error.HTTPError as e:
        return {'err': f'HTTP {e.code}'}
    except Exception as e:
        return {'err': 'timeout' if 'timed out' in str(e) else str(e)[:120]}


def probe():
    pop = load_population()
    c = get(API.format(sn=IMPOSSIBLE_SN, pks='1', date=DATES[0]))
    time.sleep(RATE_S)
    control = {'shortname': IMPOSSIBLE_SN, 'result': c.get('err') or 'HTTP 200', 'falsifiable': 'j' not in c}
    print(f'[control] {control}', file=sys.stderr)
    if not control['falsifiable']:
        sys.exit('FATAL: impossible shortname returned 200 -- instrument not falsifiable')

    by_sn = collections.OrderedDict()
    for t in pop:
        by_sn.setdefault(t['sn'], []).append(t['pk'])

    out = {'startedAt': datetime.now(timezone.utc).isoformat(), 'dates': DATES, 'population': len(pop),
           'shortnames': len(by_sn), 'control': control, 'requests': 0, 'retries': [],
           'perPk': {str(t['pk']): {'sn': t['sn'], 'probes': []} for t in pop}}

    def run(sn, pks, date, depth):
        out['requests'] += 1
        x = get(API.format(sn=sn, pks=','.join(map(str, pks)), date=date))
        time.sleep(RATE_S)
        if 'err' in x and re.search(r'timeout|HTTP 5', x['err']) and len(pks) > 1 and depth < 2:
            out['retries'].append({'sn': sn, 'date': date, 'size': len(pks), 'err': x['err'], 'split': True})
            h = (len(pks) + 1) // 2
            time.sleep(2)
            run(sn, pks[:h], date, depth + 1)
            run(sn, pks[h:], date, depth + 1)
            return
        j = x.get('j') or {}
        items = {int(it.get('id', -1)): it for it in (j.get('items') or [])}
        det = j.get('details') or {}
        for pk in pks:
            it = items.get(pk)
            p = {'date': date, 'error': x.get('err')}
            if 'err' not in x:
                p.update(absent=it is None, liveCurrency=det.get('currency'),
                          includeFees=det.get('prices_include_booking_fees'),
                          includeTaxes=det.get('prices_include_taxes'))
            if it:
                sa = (it.get('availability') or {}).get('start_at')
                p['start_at'] = sa
                p['dateValid'] = bool(sa) and sa[:10] == date
                cts = ((it.get('price') or {}).get('breakdown') or {}).get('customer_types') or []
                p['tiers'] = [{'id': ct.get('id'), 'singular': ct.get('singular'), 'plural': ct.get('plural'),
                               'note': ct.get('note'), 'priceCents': ct.get('price'), 'min': ct.get('min_party_size')}
                              for ct in cts]
            out['perPk'][str(pk)]['probes'].append(p)

    n = 0
    for sn, pks in by_sn.items():
        for i in range(0, len(pks), BATCH):
            for date in DATES:
                run(sn, pks[i:i + BATCH], date, 0)
        n += 1
        if n % 10 == 0:
            print(f'{n}/{len(by_sn)} operators, {out["requests"]} req', file=sys.stderr)
        os.makedirs(EV, exist_ok=True)
        json.dump(out, open(f'{EV}/probe.json', 'w'))
    out['finishedAt'] = datetime.now(timezone.utc).isoformat()
    bad = [k for k, v in out['perPk'].items() if len(v['probes']) != len(DATES)]
    out['reconcile'] = {'population': len(pop), 'pksWithFullProbeSet': len(pop) - len(bad), 'incomplete': bad}
    json.dump(out, open(f'{EV}/probe.json', 'w'))
    print(json.dumps({'requests': out['requests'], 'retries': len(out['retries']), 'reconcile': out['reconcile']}))


# ---------------- apply ----------------
def apply(dry):
    pop = load_population()
    ev = json.load(open(f'{EV}/probe.json'))
    if ev.get('reconcile', {}).get('incomplete'):
        sys.exit('ABORT: probe incomplete')
    if ev['population'] != len(pop):
        sys.exit('ABORT: population drift since probe')
    if not any(len({p.get('start_at') for p in v['probes'] if p.get('start_at')}) > 1 for v in ev['perPk'].values()):
        sys.exit('ABORT: date parameter ignored (no start_at moved)')

    doc = json.load(open(FILE, encoding='utf-8'))
    existing_pks = {t['pk'] for t in doc['tours']}
    for t in pop:
        if t['pk'] in existing_pks:
            sys.exit(f'ABORT: pk {t["pk"]} already in tours-data.json -- this is ingest, not refresh')

    dates = ev['dates']
    applied_at = datetime.now(timezone.utc).isoformat()
    summary, disp, sweep = [], collections.Counter(), []
    new_rows = []

    for t in pop:
        v = ev['perPk'][str(t['pk'])]
        ok = [p for p in v['probes'] if not p.get('error')]
        sampled = [p for p in ok if not p.get('absent')]
        rec = {'pk': t['pk'], 'name': t['name'], 'company': t['company'], 'sn': t['sn']}

        city = t['city']
        location = f'United States/Florida/{city}'
        island = location.lower()
        tags = [t['tags']] if t['tags'] else []
        try:
            quality = int(t['qualityScore'])
        except (TypeError, ValueError):
            quality = None

        row = {
            'id': str(t['pk']), 'pk': t['pk'], 'name': t['name'], 'company': t['company'],
            'bookingUrl': t['bookingUrl'], 'category': '', 'location': location, 'island': island,
            'price': None, 'priceLabel': '', 'priceConfidence': 'held', 'qualityScore': quality,
            'currency': SITE_CUR, 'duration': '', 'durationText': '', 'description': '',
            'descriptionRaw': '', 'descriptionQuality': '', 'highlights': [], 'tags': tags,
            'image': '', 'galleryImages': [], 'rating': None, 'reviewCount': None, 'ratingSource': '',
            'freeCancellation': True, 'timeOfDay': 'morning', 'capacity': None,
            'enrichmentSource': SOURCE, 'status': 'active', 'statusReason': None,
            'statusFirstSeen': STAMP_DAY, 'statusConsecutiveRuns': 1, 'lastUpdated': STAMP_DAY,
            'verifiedOn': STAMP_DAY,
            '_unknownFields': {
                'priceSource': SOURCE, 'origin': 'held-tours-needs-operator-key.json (retired #154)',
                'probeDates': dates, 'probeSampled': len(sampled),
                'probeDateValid': sum(1 for p in sampled if p.get('dateValid')),
                'verifiedOn': STAMP_DAY, 'verifiedDates': len(sampled),
            },
        }
        x = row['_unknownFields']

        def hold(status, basis):
            x['priceBasis'] = basis
            x['priceHold'] = status
            rec.update(disposition=status, new=None)
            disp[status] += 1
            summary.append(rec)
            new_rows.append(row)

        if not sampled:
            x['priceTiers'] = []
            st = 'UNSAMPLED' if ok else 'PROBE_ERROR'
            errs = [p['error'] for p in v['probes'] if p.get('error')]
            hold(st, f'{st}: absent from price-preview items[] on {len(ok)}/{len(dates)} dated probes '
                     f'({", ".join(dates)}) -- 60-day/4-date sweep exhausted; low never released'
                     + (f', errors {errs}' if errs else ''))
            continue

        if t['pk'] in MANUAL_HOLD:
            x['priceTiers'] = []
            hold('ambiguous_rate_codes', f'HELD (manual audit, not an engine rule): {MANUAL_HOLD[t["pk"]]}')
            continue

        key = lambda p: json.dumps([[q.get('singular'), q.get('note'), q.get('priceCents')] for q in p['tiers']])
        counts = collections.Counter(key(p) for p in sampled)
        maj_key = counts.most_common(1)[0][0]
        maj = next(p for p in sampled if key(p) == maj_key)
        valid = sum(1 for p in sampled if p.get('dateValid'))
        caveat = f'{valid} date-valid' if valid else 'evidence from next-departure echo, 0 date-valid on probe dates (D-638)'
        evid = f'{len(sampled)}/{len(dates)} dated readings {STAMP_DAY} ({caveat}), {len(counts)} ladder shape(s), live {maj.get("liveCurrency")}'
        L = [{'name': q.get('singular'), 'note': q.get('note') or '', 'price': u(q.get('priceCents') or 0),
              'minPartySize': q.get('min')} for q in maj['tiers']]
        x['priceTiers'] = L
        x['priceIncludesBookingFees'] = maj.get('includeFees')
        x['priceIncludesTaxes'] = maj.get('includeTaxes')
        ctx = t['name']
        classes = [(q, classify(q, ctx)) for q in maj['tiers']]
        if any(c == 'variant' for q, c in classes):
            inherit = 'group' if any(c == 'group' for q, c in classes) else 'base'
            classes = [(q, inherit if c == 'variant' else c) for q, c in classes]
        if sum(1 for q, c in classes if c == 'base') > 1:
            classes = [(q, 'never' if c == 'base' and re.fullmatch(r'rider|ride[- ]?along|passenger only|non[- ]?diver',
                                                                     (q.get('singular') or '').strip(), re.I) else c)
                       for q, c in classes]
        rec['tiers'] = [{'singular': q.get('singular'), 'note': q.get('note') or '', 'price': u(q.get('priceCents') or 0),
                          'min': q.get('min'), 'cls': c} for q, c in classes]
        pos = [(q, c) for q, c in classes if c != 'zero']
        ladder = ' / '.join(f'{q.get("singular")} {money(u(q["priceCents"]))}' for q, _ in pos)
        cur = maj.get('liveCurrency')

        if not pos:
            hold('zero_price', f'zero_price: every live tier is $0 on the majority reading; {evid}')
            continue
        if cur != SITE_CUR:
            a = min(pos, key=lambda pc: pc[0]['priceCents'])[0]
            x['liveAmount'] = u(a['priceCents'])
            x['liveCurrency'] = cur
            hold(f'non_usd_currency:{cur}', f'HELD (D-620): live details.currency {cur} != site USD; true amount {cur} {u(a["priceCents"])} ({a.get("singular")}) stamped, unpublished; {evid}')
            continue

        base = [q for q, c in pos if c == 'base']
        group = [q for q, c in pos if c == 'group']
        never = [q for q, c in pos if c == 'never']
        dep = [q for q, c in pos if c == 'deposit']
        if not base and not group and not never and dep:
            hold('deposit_only', f'HELD (D-644): a deposit tier is never a price -- ladder {ladder}; {evid}')
            continue

        anchor = kind = rule = None
        if len(pos) == 1 and pos[0][1] != 'deposit':
            q, c = pos[0]
            anchor = q
            rule = 'D-640 single-tier product anchors on its sole tier'
            kind = 'group' if c == 'group' else 'per-person'
        elif base:
            anchor = min(base, key=lambda q: q['priceCents'])
            kind = 'per-person'
            rule = 'D-624 cheapest adult/base per-person tier' + (f' of {len(base)} base tiers (D-625)' if len(base) > 1 else '')
        elif group:
            hc = [(headcount(q.get('singular')), q) for q in group]
            per_head = all(re.search(r'per (person|player|participant|head|adult|guest|rider|passenger|angler|diver|pp)\b',
                                      (q.get('note') or '') + ' ' + (q.get('singular') or ''), re.I) for q in group)
            hcs = [(h, q) for h, q in hc if h]
            falling = (len(hcs) >= 2 and all(a[0] != b[0] for a, b in zip(hcs, hcs[1:]))
                       and all((b[1]['priceCents'] < a[1]['priceCents']) == (b[0] > a[0])
                               for a, b in zip(sorted(hcs, key=lambda z: z[0]), sorted(hcs, key=lambda z: z[0])[1:])))
            if per_head and falling:
                anchor = max(hcs, key=lambda z: z[0])[1]
                kind = 'per-person'
                rule = 's48-R1 per-head rate ladder (price falls as band grows): largest band per-person figure anchors'
            else:
                anchor = min(group, key=lambda q: q['priceCents'])
                kind = 'group'
                rule = 'D-614 whole-boat / party-size ladder: floor total anchors (never divided by headcount)' if len(group) > 1 else 'D-614 whole-boat floor'
        else:
            hold('never_only', f'HELD (no adult/base tier): live ladder {ladder} has only never-anchor tiers; {evid}')
            continue

        manual_note = ''
        if t['pk'] in MANUAL_ANCHOR:
            want, why = MANUAL_ANCHOR[t['pk']]
            correct = next((q for q, _ in pos if (q.get('singular') or '') == want), None)
            if correct is None:
                sys.exit(f'ABORT: manual override target "{want}" not found in pk {t["pk"]} tiers')
            engine_pick = f'{anchor.get("singular")} {money(u(anchor["priceCents"]))}'
            anchor = correct
            kind = 'per-person'
            rule = 'MANUAL OVERRIDE (audited 2026-08-26): ' + why
            manual_note = f' [manual override: engine anchor was {engine_pick}]'

        lab = anchor.get('singular') or ''
        note = anchor.get('note') or ''
        if ADDON.search(lab) or (NOTE_NEVER.search(note) and re.search(r'per additional|per item', note, re.I)):
            sweep.append({'pk': t['pk'], 'label': lab, 'note': note})

        unit = unit_for('per-person' if kind == 'per-person' else 'group', lab, note, t['name'],
                         ' '.join((q.get('singular') or '') + ' ' + (q.get('note') or '') for q, _ in pos) + ' ' + t['company'])
        price = u(anchor['priceCents'])
        same = [u(q['priceCents']) for p in sampled for q in p['tiers']
                if q.get('singular') == anchor.get('singular') and (q.get('priceCents') or 0) > 0]
        lo, hi = (min(same), max(same)) if same else (price, price)
        rng = hi > lo
        if rng:
            x['observedPriceRange'] = [lo, hi]
        row['price'] = price if not rng else lo
        row['currency'] = SITE_CUR
        row['priceLabel'] = f'{money(row["price"])}{"" if not rng else "-" + money(hi)} {PHRASE[unit]}'
        row['priceConfidence'] = CONF[unit] + ('-range' if rng else '')
        x['unit'] = unit
        x['priceKind'] = 'whole boat / private charter' if unit == 'whole-boat' else ('per adult' if unit == 'per-person' else 'per unit')
        mp = anchor.get('min')
        x['minPartySize'] = mp
        if unit == 'per-person' and isinstance(mp, int) and mp > 1:
            x['minimumSpend'] = round(row['price'] * mp, 2)
        x.pop('priceHold', None)
        skipped = [f'{q.get("singular")} {money(u(q["priceCents"]))} [{c}]' for q, c in pos if q is not anchor]
        x['priceBasis'] = (f'{rule}: "{lab}" {money(price)}' + (f' (note "{note}")' if note else '') + f', unit {unit}'
                            + (f'; not anchoring: {", ".join(skipped)}' if skipped else '')
                            + (f'; anchor varied {money(lo)}-{money(hi)} across readings' if rng else '')
                            + manual_note + f'; {evid}')
        rec.update(disposition='ingested', new=row['price'], label=lab, unit=unit, rule=rule)
        disp['ingested'] += 1
        summary.append(rec)
        new_rows.append(row)

    if len(new_rows) != len(pop):
        sys.exit(f'ABORT: {len(new_rows)} rows built != {len(pop)} population')

    doc['tours'].extend(new_rows)
    doc['lastNormalized'] = STAMP_DAY

    result = {'stampedOn': STAMP_DAY, 'appliedAt': applied_at, 'population': len(pop),
              'attempted': len(pop), 'succeeded': len(summary), 'ingested': disp.get('ingested', 0),
              'disposition': dict(disp), 'addonSweep': sweep, 'summary': summary}

    os.makedirs(EV, exist_ok=True)
    if not dry:
        open(FILE, 'w', encoding='utf-8').write(json.dumps(doc, indent=2, ensure_ascii=False))
        json.dump(result, open(f'{EV}/apply-summary.json', 'w'), indent=1, ensure_ascii=False)
    else:
        json.dump(result, open(f'{EV}/apply-summary.dryrun.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: result[k] for k in ('population', 'attempted', 'succeeded', 'ingested', 'disposition')},
                      ensure_ascii=False), 'dry' if dry else 'WRITTEN')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'probe':
        probe()
    elif mode == 'apply':
        apply('--dry-run' in sys.argv)
    else:
        sys.exit('usage: probe|apply [--dry-run]')

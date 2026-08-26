"""Apply half of s50-fst-refresh (imported by scripts/s50-fst-refresh.py). Rules and stamps documented there."""
import collections, json, re, sys
from datetime import datetime, timezone

EV = 'scripts/evidence/s50-fst-refresh'
SOURCE, STAMP_DAY, SITE_CUR = 's50-fst-refresh', '2026-08-25', 'USD'
def u(c):
    v = round(c / 100.0, 2)
    return int(v) if v == int(v) else v
def money(n): return f'${n:,.0f}' if abs(n - round(n)) < 0.005 else f'${n:,.2f}'

# ---- tier classification (WENG s48 classifyTier, verbatim lineage; + deposit + add-on shapes for D-644 / D-637 / D-639) ----
NEVER = re.compile(r"\b(child|childs|child's|children|childrens|children's|kid|kids|kid's|infant|infants|baby|babies|toddler|junior|juniors|youth|youths|teen|teenager|teens|adolescent|adolescents|young adult|student|students|senior|seniors|oap|concession|concessions|pensioner|disabled|wheelchair|carer|companion|military|veteran|veterans|discount|under\s*\d+s?|\d+\s*(and|&)\s*under|family|families|add[- ]?on|extra|extras|additional|supplement|upgrade|gratuity|tip|tips|donation|deposit|voucher|gift card|redemption|per additional|spectator|non[- ]?participant|rider[- ]?along|ride[- ]?along|observer|dog|dogs|pet|pets|kit|merchandise|parking|niño|niños|niña|niñas|bebé|bebe|infante)\b", re.I)
AGE_RANGE = re.compile(r'\b\d{1,2}\s*(-|–|to)\s*\d{1,2}\s*(yrs|years|year olds|yr olds|y/o|yo|años)\b', re.I)
WORDNUM = r'(two|three|four|five|six|seven|eight|nine|ten|twelve|\d+)'
GROUP = re.compile(r'\b(per group|group|groups|party|parties|package|packages|bundle|private|exclusive|charter|boat|vessel|pontoon|yacht|catamaran|sailboat|vehicle|car|van|cart|table|room|cabin|pod|lane|court|couple|couples|for two|for 2|whole|hire|rental|raft|canoe|kayak|jet ?ski|waverunner|paddleboard|paddle board|sup|seater|capacity|up to \d+|' + WORDNUM + r'\s*(people|persons|ppl|pax|guests|players|riders|passengers|adults|anglers|divers))\b', re.I)
BASE_WORDS = 'adult|adults|person|per person|standard|general|guest|guests|visitor|participant|passenger|rider|player|ticket|seat|seating|admission|individual|one person|1 person|per seat|angler|diver|snorkeler|paddler|swimmer'
BASE = re.compile(r'\b(' + BASE_WORDS + r')\b', re.I)
BASE_HEAD = re.compile(r'^(' + BASE_WORDS + r')\b', re.I)
PER_PERSON = re.compile(r'\b(per (person|player|participant|head|adult|guest|rider|passenger|angler|diver|pp))\b|\beach person\b|\bpp\b|\b(1|one) (person|player)\b(?!\s*(or|to|-|–))', re.I)
ORDINAL = re.compile(r'\b(2nd|3rd|4th|5th|6th|second|third|fourth|fifth|sixth)\s+(rider|person|passenger|guest|adult|diver)\b', re.I)
NOTE_NEVER = re.compile(r'^\s*extras?\b|\ban (optional )?extra\b|\bprice per item\b|\badd[- ]on\b|\bper additional\b', re.I)
VOLUME = re.compile(r'^(' + WORDNUM + r'\s*(people|persons|adults|guests|players|passengers|anglers|divers)|groups? of|([2-9]|\d{2,})\s*(-|–|to|\+)\s*\d*\s*(people|persons|adults|guests|players|passengers|anglers))\b', re.I)
NAME_GROUP = re.compile(r'\b(hire|rental|rentals|charter|charters|private|boat|pontoon|yacht|vessel|jet ?ski|waverunner|kayak|paddleboard|sailboat|catamaran)\b', re.I)
DEPOSIT = re.compile(r'\bdeposit\b|\bdepósito\b|\bbalance due\b', re.I)
ACCESSORY = re.compile(r'\b(adaptor|adapter|boots?|gloves?|hoods?|wetsuit|cooler|dry bag|life ?jacket|fishing (pole|rod|license)|bait|ice|fuel|gas|tube|towable|anchor|umbrella|chair|cabana rental|photo|photos|video|gopro|snorkel gear|gear rental|extra person|extra participants?)\b', re.I)
ADDON = re.compile(r'per additional|\badditional\b|\bextra\b|\badd[- ]?on\b|\bsupplement\b|\bper item\b', re.I)
VEHICLE = re.compile(r'\b(jet ?ski|waverunner|kayak|kayaks|paddle ?board|sup|canoe|bike|scooter|golf cart|craft|tube|seabob|efoil|e-foil)\b', re.I)
BOAT = re.compile(r'\b(charter|charters|boat|boats|pontoon|yacht|vessel|sail|sailing|sailboat|catamaran|private|whole|skiff|bay boat|deck boat|cruise|airboat|fishing|offshore|inshore|sandbar|reef|wreck|anglers?)\b', re.I)
HEADCOUNT = re.compile(r'\b(\d+)\s*(people|persons|ppl|pax|guests|players|riders|passengers|adults|anglers|divers)\b|\b(people|persons|guests|passengers|adults)\s*(of\s*)?(\d+)\b|\bup to (\d+)\b|\b(\d+)\s*[-–]\s*(\d+)\b', re.I)
WORD2N = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'twelve': 12}

def classify(tier, product_name):
    sing = (tier.get('singular') or '').strip(); note = tier.get('note') or ''
    if not ((tier.get('priceCents') or 0) > 0): return 'zero'
    if DEPOSIT.search(sing) or DEPOSIT.search(note): return 'deposit'
    if NEVER.search(sing) or AGE_RANGE.search(sing): return 'never'
    if ACCESSORY.search(sing) and not ACCESSORY.search(product_name or ''): return 'never'   # s49: accessory tiers never anchor unless the product IS the accessory
    if NOTE_NEVER.search(note) or ORDINAL.search(sing): return 'never'                      # "3rd Rider" is an additional-person add-on (D-637)
    if VOLUME.search(sing): return 'group'
    if BASE_HEAD.search(sing): return 'base'
    if BASE.search(sing) and not GROUP.search(sing): return 'base'
    if GROUP.search(sing): return 'group'                                                     # a group-shaped LABEL wins over a per-person add-on note ("Includes 12 Guests, then $50 per person")
    if PER_PERSON.search(note): return 'base'
    if GROUP.search(note): return 'group'
    if NAME_GROUP.search(product_name or ''): return 'group'
    return 'variant'   # unnamed variant ("Half Day", "Bride Experience"): inherits its ladder's class — group if any sibling is group, else per-person base (D-625)

def headcount(s):
    m = re.search(r'\b(' + '|'.join(WORD2N) + r')\b', s or '', re.I)
    if m: return WORD2N[m.group(1).lower()]
    m = HEADCOUNT.search(s or '')
    if not m: return None
    nums = [int(g) for g in m.groups() if g and g.isdigit()]
    return max(nums) if nums else None

def unit_for(kind, label, note, product, siblings=''):
    """CardFormat.unitPhrase vocabulary: whole-boat | per-vehicle | per-unit | per-person."""
    if kind == 'per-person': return 'per-person'
    s = f'{label} {note} {product}'
    if VEHICLE.search(label) or VEHICLE.search(note): return 'per-vehicle'
    if BOAT.search(s): return 'whole-boat'
    if VEHICLE.search(product): return 'per-vehicle'
    if BOAT.search(siblings): return 'whole-boat'      # sibling tiers name the vessel ("OFFSHORE 6 HOUR CHARTER" beside "Offshore fishing 5 hour")
    return 'per-unit'

CONF = {'per-person': 'verified-adult', 'whole-boat': 'verified-whole-boat', 'per-unit': 'verified-whole-unit', 'per-vehicle': 'verified-whole-unit'}
PHRASE = {'per-person': 'per person', 'whole-boat': 'whole boat', 'per-unit': 'per unit', 'per-vehicle': 'per craft'}

def apply(load, dry):
    doc, pop = load()
    ev = json.load(open(f'{EV}/probe.json'))
    if ev.get('reconcile', {}).get('incomplete'): sys.exit('ABORT: probe incomplete')
    if ev['population'] != len(pop): sys.exit('ABORT: population drift since probe')
    if not any(len({p.get('start_at') for p in v['probes'] if p.get('start_at')}) > 1 for v in ev['perPk'].values()):
        sys.exit('ABORT: date parameter ignored (no start_at moved)')
    dates = ev['dates']; applied_at = datetime.now(timezone.utc).isoformat()
    before = {t['pk']: json.dumps(t, sort_keys=True) for t in doc['tours']}
    pop_pks = {t['pk'] for t in pop}
    summary, disp, sweep = [], collections.Counter(), []
    for t in pop:
        v = ev['perPk'][str(t['pk'])]; ok = [p for p in v['probes'] if not p.get('error')]; sampled = [p for p in ok if not p.get('absent')]
        x = t.setdefault('_unknownFields', {})
        old = {'price': t.get('price'), 'label': t.get('priceLabel'), 'conf': t.get('priceConfidence')}
        rec = {'pk': t['pk'], 'name': t['name'], 'company': t['company'], 'sn': v['sn'], 'old': old['price'], 'oldLabel': old['label'], 'oldConf': old['conf']}
        for k in ('observedPriceRange', 'minimumSpend', 'unit', 'priceBasisNote', 'singleObservation', 'priceVolatility'): x.pop(k, None)
        x['priceSource'] = SOURCE; x['liveCurrency'] = next((p.get('liveCurrency') for p in ok if p.get('liveCurrency')), None)
        x['probeDates'] = dates; x['probeSampled'] = len(sampled); x['probeDateValid'] = sum(1 for p in sampled if p.get('dateValid'))
        t['verifiedOn'] = STAMP_DAY; t['lastUpdated'] = STAMP_DAY; x['verifiedOn'] = STAMP_DAY; x['verifiedDates'] = len(sampled)
        def hold(status, basis):
            t['price'] = None; t['priceLabel'] = ''; t['priceConfidence'] = 'held'
            x['priceBasis'] = basis; x['priceHold'] = status; x.pop('minPartySize', None)
            rec.update(disposition=status, new=None); disp[status] += 1; summary.append(rec)
        stored = f'{money(old["price"])}{" (" + old["label"] + ")" if old["label"] else ""}'
        if not sampled:
            x['priceTiers'] = []
            st = 'UNSAMPLED' if ok else 'PROBE_ERROR'
            errs = [p['error'] for p in v['probes'] if p.get('error')]
            hold(st, f'{st}: absent from price-preview items[] on {len(ok)}/{len(dates)} dated probes ({", ".join(dates)})' + (f', errors {errs}' if errs else '') + f'; stored {stored} suppressed pending a live reading; unsampled is never published')
            rec['probeErrors'] = errs; continue
        key = lambda p: json.dumps([[q.get('singular'), q.get('note'), q.get('priceCents')] for q in p['tiers']])
        counts = collections.Counter(key(p) for p in sampled); maj_key = counts.most_common(1)[0][0]; maj = next(p for p in sampled if key(p) == maj_key)
        valid = sum(1 for p in sampled if p.get('dateValid'))
        caveat = f'{valid} date-valid' if valid else 'evidence from next-departure echo, 0 date-valid on probe dates (D-638)'
        evid = f'{len(sampled)}/{len(dates)} dated readings {STAMP_DAY} ({caveat}), {len(counts)} ladder shape(s), live {maj.get("liveCurrency")}'
        L = [{'name': q.get('singular'), 'note': q.get('note') or '', 'price': u(q.get('priceCents') or 0), 'minPartySize': q.get('min')} for q in maj['tiers']]
        x['priceTiers'] = L; x['priceIncludesBookingFees'] = maj.get('includeFees'); x['priceIncludesTaxes'] = maj.get('includeTaxes')
        ctx = ' '.join(str(t.get(k) or '') for k in ('name', 'durationText'))   # descriptions live in durationText (FST memory); the operator name is NOT context ("Jetski Rentals" sells parasailing per person)
        classes = [(q, classify(q, ctx)) for q in maj['tiers']]
        if any(c == 'variant' for q, c in classes):
            # unnamed variants inherit: a group sibling, or the row's prior whole-boat verification (fh-wholeboat-recovery, July), makes them whole-unit; else per-person base
            inherit = 'group' if any(c == 'group' for q, c in classes) or str(old['conf']).startswith('verified-whole-boat') or 'whole boat' in str(old['label']).lower() else 'base'
            classes = [(q, inherit if c == 'variant' else c) for q, c in classes]
        # a bare "Rider" beside another base tier is a ride-along (non-participant) and never anchors; alone, it is the participant (parasail)
        if sum(1 for q, c in classes if c == 'base') > 1:
            classes = [(q, 'never' if c == 'base' and re.fullmatch(r'rider|ride[- ]?along|passenger only|non[- ]?diver', (q.get('singular') or '').strip(), re.I) else c) for q, c in classes]
        rec['tiers'] = [{'singular': q.get('singular'), 'note': q.get('note') or '', 'price': u(q.get('priceCents') or 0), 'min': q.get('min'), 'cls': c} for q, c in classes]
        pos = [(q, c) for q, c in classes if c != 'zero']
        ladder = ' / '.join(f'{q.get("singular")} {money(u(q["priceCents"]))}' for q, _ in pos)
        cur = maj.get('liveCurrency')
        if not pos:
            hold('zero_price', f'zero_price: every live tier is $0 on the majority reading ({" / ".join(q["name"] for q in L)}); {evid}; stored {stored} suppressed (D-575)'); continue
        if cur != SITE_CUR:
            a = min(pos, key=lambda pc: pc[0]['priceCents'])[0]; x['liveAmount'] = u(a['priceCents'])
            hold(f'non_usd_currency:{cur}', f'HELD (D-620): live details.currency {cur} ≠ site USD; true amount {cur} {u(a["priceCents"])} ({a.get("singular")}) stamped, unpublished; {evid}'); continue
        base = [q for q, c in pos if c == 'base']; group = [q for q, c in pos if c == 'group']; never = [q for q, c in pos if c == 'never']; dep = [q for q, c in pos if c == 'deposit']
        if not base and not group and not never and dep:
            hold('deposit_only', f'HELD (D-644): a deposit tier is never a price — ladder {ladder}; {evid}; stored {stored} suppressed'); continue
        anchor = kind = rule = None
        if len(pos) == 1 and pos[0][1] != 'deposit':
            q, c = pos[0]; anchor = q; rule = 'D-640 single-tier product anchors on its sole tier'
            kind = 'group' if c == 'group' else 'per-person'   # class already carries context + prior verification
        elif base:
            anchor = min(base, key=lambda q: q['priceCents']); kind = 'per-person'
            rule = f'D-624 cheapest adult/base per-person tier' + (f' of {len(base)} base tiers (D-625)' if len(base) > 1 else '')
        elif group:
            # ladder direction: per-head rate ladder (price FALLS as band grows, note says per person) -> s48-R1; otherwise D-614 floor total
            hc = [(headcount(q.get('singular')), q) for q in group]
            per_head = all(PER_PERSON.search(q.get('note') or '') or PER_PERSON.search(q.get('singular') or '') for q in group)
            hcs = [(h, q) for h, q in hc if h]
            falling = len(hcs) >= 2 and all(a[0] != b[0] for a, b in zip(hcs, hcs[1:])) and all((b[1]['priceCents'] < a[1]['priceCents']) == (b[0] > a[0]) for a, b in zip(sorted(hcs, key=lambda z: z[0]), sorted(hcs, key=lambda z: z[0])[1:]))
            if per_head and falling:
                anchor = max(hcs, key=lambda z: z[0])[1]; kind = 'per-person'; rule = 's48-R1 per-head rate ladder (price falls as band grows): largest band per-person figure anchors'
            else:
                anchor = min(group, key=lambda q: q['priceCents']); kind = 'group'
                rule = 'D-614 whole-boat / party-size ladder: floor total anchors (never divided by headcount)' if len(group) > 1 else 'D-614 whole-boat floor'
        else:
            hold('never_only', f'HELD (no adult/base tier): live ladder {ladder} has only never-anchor tiers (child/concession/add-on); pending ruling; {evid}; stored {stored} suppressed'); continue
        lab = anchor.get('singular') or ''; note = anchor.get('note') or ''
        if ADDON.search(lab) or NOTE_NEVER.search(note) or ADDON.search(note) and re.search(r'per additional|per item', note, re.I):
            sweep.append({'pk': t['pk'], 'label': lab, 'note': note})
        unit = unit_for('per-person' if kind == 'per-person' else 'group', lab, note, t['name'], ' '.join((q.get('singular') or '') + ' ' + (q.get('note') or '') for q, _ in pos) + ' ' + str(t.get('company') or ''))
        price = u(anchor['priceCents'])
        # range across sampled readings for the same anchor label (the -range confidence class already in this repo)
        same = [u(q['priceCents']) for p in sampled for q in p['tiers'] if q.get('singular') == anchor.get('singular') and (q.get('priceCents') or 0) > 0]
        lo, hi = (min(same), max(same)) if same else (price, price)
        rng = hi > lo
        if rng: x['observedPriceRange'] = [lo, hi]
        t['price'] = price if not rng else lo; t['currency'] = SITE_CUR
        t['priceLabel'] = f'{money(t["price"])}{"–" + money(hi) if rng else ""} {PHRASE[unit]}'
        t['priceConfidence'] = CONF[unit] + ('-range' if rng else '')
        x['unit'] = unit; x['priceKind'] = 'whole boat / private charter' if unit == 'whole-boat' else ('per adult' if unit == 'per-person' else 'per unit')
        mp = anchor.get('min'); x['minPartySize'] = mp
        if unit == 'per-person' and isinstance(mp, int) and mp > 1: x['minimumSpend'] = round(price * mp, 2)
        x.pop('priceHold', None)
        skipped = [f'{q.get("singular")} {money(u(q["priceCents"]))} [{c}]' for q, c in pos if q is not anchor]
        x['priceBasis'] = f'{rule}: "{lab}" {money(price)}' + (f' (note "{note}")' if note else '') + f', unit {unit}' + (f'; not anchoring: {", ".join(skipped)}' if skipped else '') + (f'; anchor varied {money(lo)}–{money(hi)} across readings' if rng else '') + f'; {evid}'
        changed = old['price'] != t['price']
        d = 'repriced' if changed else 'unchanged'
        rec.update(disposition=d, new=t['price'], label=lab, unit=unit, rule=rule, delta=(None if not changed else round(t['price'] - float(old['price']), 2))); disp[d] += 1; summary.append(rec)
    if sweep:
        json.dump(sweep, open(f'{EV}/addon-abort.json', 'w'), indent=1); sys.exit(f'ABORT (D-639): add-on-shaped anchor tier(s) {len(sweep)} — see {EV}/addon-abort.json')
    for t in pop: t.pop('_sn', None)
    after = {t['pk']: json.dumps(t, sort_keys=True) for t in doc['tours']}
    changed = [pk for pk in after if after[pk] != before[pk]]
    outside = [pk for pk in changed if pk not in pop_pks]
    if outside or len(after) != len(before): sys.exit(f'ABORT: rows outside population changed {outside[:5]}')
    result = {'stampedOn': STAMP_DAY, 'appliedAt': applied_at, 'population': len(pop), 'attempted': len(pop), 'succeeded': len(summary), 'rowsChanged': len(changed), 'untouchedInPop': len(pop) - len(changed), 'disposition': dict(disp), 'summary': summary}
    if len(summary) != len(pop): sys.exit('ABORT: attempted != succeeded')
    if not dry:
        open('tours-data.json', 'w', encoding='utf-8').write(json.dumps(doc, indent=2, ensure_ascii=False))
        json.dump(result, open(f'{EV}/apply-summary.json', 'w'), indent=1, ensure_ascii=False)
    else:
        json.dump(result, open(f'{EV}/apply-summary.dryrun.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: result[k] for k in ('population', 'attempted', 'succeeded', 'rowsChanged', 'untouchedInPop', 'disposition')}, ensure_ascii=False), 'dry' if dry else 'WRITTEN')

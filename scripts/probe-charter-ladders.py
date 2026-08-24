#!/usr/bin/env python3
"""D-574/D-600 — live FareHarbor probe of the priceLabel=='charter' population (FST port of KWST #240).

READ-ONLY. Writes a JSON observation file; never touches tours-data.json.

WHY THIS EXISTS
  The `charter` priceLabel is the unique fingerprint of extract-price-v5.2.js's
  charter branch, which selects `Math.max(...allPrices)` — the ceiling of the
  page's dollar figures. Every other price writer in the network selects the
  floor. This script re-reads the real customer-type ladder so the ceiling
  picks can be separated from the ones that are correct by construction.

INSTRUMENT RULES (each one exists because its absence produced a wrong reading)
  * DATE VALIDITY. availability.start_at echoes the NEXT departure on/after the
    requested date, not the requested date. A reading is VALID only when
    start_at[0:10] == the requested date; everything else is a fallback echo and
    is DISCARDED rather than counted. Without this, one departure gets counted
    17 times and a one-date product looks fully sampled.
  * $0 TIERS ARE NOT FARES (D-575). "Call to Book!" tiers price at 0. They are
    excluded from floor AND ceiling, never averaged in.
  * ABSENCE IS UNSAMPLED, NEVER ZERO. An item missing from items[] means the
    operator published no availability for that date.
  * THE ITEM KEY IS `id`, NOT `pk`. Matching on "pk" silently reads every item
    as absent and makes a live product look dead.
  * TIER ID IS NOT A KEY. Six Fins reuses ids 973441/973442/973443 across three
    different items at three different prices. Products are keyed on the tuple
    (id, singular, note, min_party_size) so a reused id cannot collide.
  * MIN_VALID readings required, else INSUFFICIENT — a single reading cannot
    distinguish a stable ladder from a one-off.
  * A wrong company shortname 400s/404s identically to a dead product, so the
    HTTP status of every distinct shortname is recorded for adjudication.

FALSIFIABILITY. A deliberately impossible shortname is probed first; if it
returns 200 the instrument cannot discriminate and the run aborts.
"""
import argparse, collections, json, sys, time, urllib.error, urllib.request
from datetime import date, timedelta

API = ("https://fareharbor.com/api/embed/{sn}/price-preview/per-item/v2/"
       "?item_pks={pks}&include_breakdown=yes&date={date}")
UA = "WanderRenderMonitor/1.0 (+internal-qa)"
BATCH = 20
MIN_VALID = 3
IMPOSSIBLE_SN = "definitely-not-a-real-fh-shortname-zzz"


def build_dates(anchor):
    """14 consecutive days from the anchor, then +30/+60/+90."""
    d0 = date.fromisoformat(anchor)
    out = [(d0 + timedelta(days=i)).isoformat() for i in range(14)]
    out += [(d0 + timedelta(days=n)).isoformat() for n in (30, 60, 90)]
    return out


def fetch(sn, pks, day):
    url = API.format(sn=sn, pks=",".join(str(p) for p in pks), date=day)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Referer": f"https://fareharbor.com/embeds/book/{sn}/"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        return e.code, None, f"HTTP {e.code}"
    except Exception as e:                                   # noqa: BLE001
        return None, None, str(e)[:140]


def tiers_of(item):
    """Non-$0 customer types, keyed on the full tuple. Tier id is NOT a key."""
    br = ((item.get("price") or {}).get("breakdown") or {})
    out = []
    zeros = []
    for c in br.get("customer_types") or []:
        cents = c.get("price")
        if not isinstance(cents, (int, float)):
            continue
        key = (c.get("id"), c.get("singular"), c.get("note"), c.get("min_party_size"))
        if cents == 0:
            zeros.append(key)                                # D-575: not a fare
            continue
        out.append({"key": list(key), "singular": c.get("singular"),
                    "note": c.get("note"), "min_party_size": c.get("min_party_size"),
                    "tier_id": c.get("id"), "dollars": cents / 100.0})
    return out, zeros


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--anchor", required=True, help="first of the 14 consecutive dates, YYYY-MM-DD")
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    dates = build_dates(args.anchor)
    targets = json.load(open(args.targets))

    code, _, err = fetch(IMPOSSIBLE_SN, [1], dates[0])
    print(f"[control] impossible shortname -> code={code} err={err}", file=sys.stderr)
    if code == 200:
        sys.exit("FATAL: bogus shortname returned 200 — instrument is not falsifiable")

    bysn = collections.defaultdict(list)
    for t in targets:
        bysn[t["sn"]].append(t["pk"])

    obs = collections.defaultdict(dict)      # pk -> {date: reading}
    httpcodes = collections.defaultdict(dict)
    for di, day in enumerate(dates, 1):
        for sn in sorted(bysn):
            pks = sorted(set(bysn[sn]))
            for j in range(0, len(pks), BATCH):
                chunk = pks[j:j + BATCH]
                status, body, ferr = fetch(sn, chunk, day)
                for pk in chunk:
                    httpcodes[pk][day] = status
                if ferr or not body or not body.lstrip().startswith("{"):
                    for pk in chunk:
                        obs[pk][day] = {"status": "ERROR", "err": ferr or "non-JSON body"}
                    time.sleep(args.sleep)
                    continue
                data = json.loads(body)
                seen = {}
                for it in data.get("items") or []:
                    seen[int(it.get("id", -1))] = it          # key is `id`, not `pk`
                for pk in chunk:
                    it = seen.get(pk)
                    if it is None:
                        obs[pk][day] = {"status": "UNSAMPLED"}
                        continue
                    start_at = (it.get("availability") or {}).get("start_at")
                    tiers, zeros = tiers_of(it)
                    valid = bool(start_at) and start_at[0:10] == day
                    obs[pk][day] = {
                        "status": "OK" if valid else "FALLBACK",
                        "start_at": start_at, "requested": day,
                        "date_valid": valid, "tiers": tiers, "zero_tiers": zeros,
                        "low": (it.get("price") or {}).get("low"),
                        "high": (it.get("price") or {}).get("high"),
                    }
                time.sleep(args.sleep)
        print(f"  ...date {di}/{len(dates)} ({day}) done", file=sys.stderr)

    json.dump({"dates": dates, "anchor": args.anchor, "min_valid": MIN_VALID,
               "control": {"shortname": IMPOSSIBLE_SN, "code": code,
                           "falsifiable": code != 200},
               "obs": {str(k): v for k, v in obs.items()},
               "http": {str(k): v for k, v in httpcodes.items()}},
              open(args.out, "w"), indent=1)
    print(f"WROTE {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

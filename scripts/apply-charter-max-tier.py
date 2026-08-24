#!/usr/bin/env python3
"""D-574/D-600/D-601 — correct Math.max charter prices from probe evidence (FST port of KWST #240).

DETERMINISTIC. Reads tours-data.json + the probe evidence file, rewrites ONLY the
rows that carry the Math.max fingerprint, and proves (a) the serializer round-trips
the file byte-for-byte before any edit (D-599), (b) every non-target row is
byte-identical after the edit, (c) the row count is unchanged.

CLASSIFICATION (derived from evidence, never hand-entered)
  correct-by-construction  single non-$0 tier, or stored == ladder floor
  duration-matched (D-601) >1 tier, stored == ladder ceiling, and durationText
                           names exactly one tier by hour count -> price = that tier
  max-tier (D-597)         >1 tier, stored == ceiling, no duration match ->
                           price = ladder floor  (none in this run; kept for the
                           fingerprint's other shape)
  stale-single-tier        single tier, stored != live. NOT the fingerprint; named,
                           untouched (D-600: the Math.max branch only).
  INSUFFICIENT             < min_valid date-valid readings; untouched, named.

Usage:
  python3 scripts/apply-charter-max-tier.py --evidence data/charter-probe-2026-08-24.json \
      --targets data/charter-probe-targets-2026-08-24.json [--write]
Without --write it prints the classification table and exits without touching the file.
"""
import argparse, json, re, sys

DATA = "tours-data.json"
HOURS = re.compile(r"(\d+)\s*[- ]?\s*hours?\b", re.I)


def dump(obj):
    # Established by measurement: indent=2, ensure_ascii=False, no trailing newline.
    return json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")


def hours_of(text):
    m = HOURS.search(text or "")
    return int(m.group(1)) if m else None


def ladder(obs, min_valid):
    """{tier_key: price} over date-valid readings only; $0 tiers already excluded."""
    tiers, valid = {}, 0
    for o in obs.values():
        if o.get("status") != "OK":
            continue
        valid += 1
        for t in o["tiers"]:
            k = (t["singular"], t["note"] or "", t["min_party_size"])
            tiers.setdefault(k, set()).add(t["dollars"])
    return tiers, valid


def classify(row, tiers, valid, min_valid):
    stored = row["price"]
    if valid < min_valid or not tiers:
        return "INSUFFICIENT", None, f"{valid} valid readings"
    prices = {k: min(v) for k, v in tiers.items()}      # per-tier floor across dates
    lo, hi = min(prices.values()), max(prices.values())
    if len(prices) == 1:
        live = lo
        if stored == live or stored in next(iter(tiers.values())):
            return "correct-by-construction", None, f"single tier {live:g}"
        return "stale-single-tier", None, f"single tier live {live:g} != stored {stored} (not the fingerprint)"
    if stored == lo:
        return "correct-by-construction", None, f"stored == floor of {len(prices)} tiers"
    if stored != hi:
        return "INSUFFICIENT", None, f"stored {stored} matches neither floor {lo:g} nor ceiling {hi:g}"
    want = hours_of(row.get("durationText"))
    hits = [(k, p) for k, p in prices.items() if want is not None and hours_of(k[0] + " " + k[1]) == want]
    if len(hits) == 1:
        (k, p), = hits
        return "duration-matched", p, f"durationText {want}h -> tier {k[0]!r} {p:g}"
    return "max-tier", lo, f"stored == ceiling {hi:g}; no unique duration match; floor {lo:g}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    raw = open(DATA, "rb").read()
    doc = json.loads(raw)
    if dump(doc) != raw:
        sys.exit("FATAL: serializer does not round-trip tours-data.json byte-for-byte (D-599)")
    ev = json.load(open(a.evidence))
    if not ev["control"]["falsifiable"]:
        sys.exit("FATAL: evidence file's control probe was not falsifiable")
    targets = {t["pk"] for t in json.load(open(a.targets))}
    rows = doc["tours"]
    charter = [r for r in rows if r.get("priceLabel") == "charter"]
    if {r["pk"] for r in charter} != targets:
        sys.exit(f"FATAL: charter population {sorted(r['pk'] for r in charter)} != targets {sorted(targets)}")

    before = {r["pk"]: dump(r) for r in rows}
    n_before = len(rows)
    changes = []
    print(f"{'pk':>7} {'class':<24} {'old':>6} {'new':>6}  name / reason")
    for r in charter:
        tiers, valid = ladder(ev["obs"][str(r["pk"])], ev["min_valid"])
        cls, new, why = classify(r, tiers, valid, ev["min_valid"])
        old = r["price"]
        if new is not None and new != old:
            if a.write:
                r["price"] = int(new) if float(new).is_integer() else new
            changes.append((r["pk"], old, new))
        print(f"{r['pk']:>7} {cls:<24} {old:>6} {'' if new is None else f'{new:g}':>6}  {r['name']} — {why}")

    if not a.write:
        print(f"\nDRY RUN: {len(changes)} row(s) would change. Re-run with --write.")
        return
    assert len(rows) == n_before, "row count changed"
    changed = {pk for pk, _, _ in changes}
    for r in rows:
        if r["pk"] not in changed:
            assert dump(r) == before[r["pk"]], f"non-target row {r['pk']} mutated"
    out = dump(doc)
    open(DATA, "wb").write(out)
    # Prove the write is exactly the intended delta and nothing else.
    check = json.loads(open(DATA, "rb").read())
    assert dump(check) == out and len(check["tours"]) == n_before
    print(f"\nWROTE {DATA}: {len(changes)} row(s) changed, {n_before - len(changes)} byte-identical, {n_before} rows total")


if __name__ == "__main__":
    main()

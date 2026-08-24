#!/usr/bin/env python3
"""Residue of FST #149 (D-574/D-600): provenance stamps on the 4 corrected rows and
the stale-single-tier Killen Time 4, all from #149's own tracked evidence.

DETERMINISTIC (D-599). No network, no clock reads. Input is the tracked probe
file data/charter-probe-2026-08-24.json; every written value is derived from
its date-valid readings (status == "OK"; FALLBACK/UNSAMPLED discarded; $0 tiers
already excluded by the probe per D-575 and listed in zero_tiers). The script
proves the serializer round-trips the file byte-for-byte before editing, then
asserts 3,603 rows, exactly the 8 target rows differ, and `price` moves only on
the Killen Time 4. Re-run after --write reports 0 modified.

PART 1 — provenance (541394, 554262, 563185, 104492). #149 wrote `price` only.
  KWST #240's 4-field convention in this repo's existing vocabulary:
    _unknownFields.priceSource   -> this script + evidence file (D-602)
    _unknownFields.priceBasis    -> the ruling in words, naming the tier
    _unknownFields.boatTiers     -> the full live ladder, floor first
    priceConfidence              -> 'high'
  No `unit`/`priceLabel`/`verified-whole-boat` is written (D-596: no vessel
  assertion in the evidence). No field name is invented.

PART 2 — stale-single-tier (613369, 613373, 613379, 613382). One live tier
  ("Private Charter", "Base price includes 6 people • Up to 18 people total"),
  stable across all 16 date-valid readings, stored equals neither endpoint:
  1200->1500, 1800->2000, 2300->2500, 2700->3000. Same 4 stamps.

EVIDENCE EXTRACT (D-595). --extract writes data/charter-residue-evidence-2026-08-24.json:
  per pk, the tier ladder, the exact dates whose readings justify it, the
  discarded dates, and the $0 tiers. Regenerates byte-identically.
"""
import argparse, collections, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOURS = REPO / "tours-data.json"
PROBE = REPO / "data" / "charter-probe-2026-08-24.json"
EXTRACT = REPO / "data" / "charter-residue-evidence-2026-08-24.json"
SRC = ("scripts/apply-charter-residue.py <- data/charter-probe-2026-08-24.json "
       "(FareHarbor price-preview per-item v2, include_breakdown=yes, 17 dates, date-validity gated)")
MIN_VALID = 12
ROWS = 3603

# pk -> (part, expected stored price, chosen tier singular, ruling)
PLAN = {
    541394: (1, 1395.0, "Half-Day Charter",
             "D-600 class (b): durationText '4 hours' names the floor tier; #149 corrected the $1,795 Full-Day ceiling to this floor"),
    554262: (1, 1395.0, "6 Hour Private Charter",
             "D-600 class (b): durationText '6 Hour' names the floor tier; #149 corrected the $1,895 10 Hour ceiling to this floor"),
    563185: (1, 1295.0, "6 Hour Private Charter",
             "D-600 class (b): durationText '6 Hour' names the floor tier; #149 corrected the $1,670 10 Hour ceiling to this floor"),
    104492: (1, 1750.0, "10 Hour Charter",
             "D-600 class (d)/D-601: durationText '10 Hour Charter' names this middle tier; #149 corrected the $1,950 12 Hour ceiling to it, not to the $1,050 floor"),
    613369: (2, 1200.0, "Private Charter",
             "stale-single-tier: one live tier, stored $1,200 equals neither endpoint; repriced to the live tier"),
    613373: (2, 1800.0, "Private Charter",
             "stale-single-tier: one live tier, stored $1,800 equals neither endpoint; repriced to the live tier"),
    613379: (2, 2300.0, "Private Charter",
             "stale-single-tier: one live tier, stored $2,300 equals neither endpoint; repriced to the live tier; a $0 'Private Charter' echo was discarded (D-575)"),
    613382: (2, 2700.0, "Private Charter",
             "stale-single-tier: one live tier, stored $2,700 equals neither endpoint; repriced to the live tier; a $0 'Private Charter' echo was discarded (D-575)"),
}
# ints: the file stores integer literals and a float would re-spell them (1395 -> 1395.0).
KILLEN_NEW = {613369: 1500, 613373: 2000, 613379: 2500, 613382: 3000}


def dump(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False)


def ladder_from(obs):
    tiers, valid_dates, dropped, zeros = collections.OrderedDict(), [], {}, set()
    for day in sorted(obs):
        o = obs[day]
        if o.get("status") != "OK":
            dropped[day] = o.get("status")
            continue
        valid_dates.append(day)
        for t in o["tiers"]:
            k = (t["singular"], t["note"] or "", t["min_party_size"])
            tiers.setdefault(k, []).append(t["dollars"])
        for z in o.get("zero_tiers") or []:
            zeros.add((z[1], z[2] or ""))
    rows = [{"singular": k[0], "note": k[1], "minPartySize": k[2],
             "price": min(v), "priceMax": max(v), "datesQuoting": len(v)} for k, v in tiers.items()]
    rows.sort(key=lambda r: (r["price"], r["singular"]))
    return rows, valid_dates, dropped, sorted(zeros)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--extract", action="store_true", help="write the evidence extract")
    args = ap.parse_args()

    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    assert probe["control"]["falsifiable"], "probe control not falsifiable"
    raw = TOURS.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert dump(doc) == raw, "tours-data.json does not round-trip byte-for-byte"
    rows = doc["tours"]
    assert len(rows) == ROWS
    by_pk = {r["pk"]: r for r in rows}
    before = {r["pk"]: json.dumps(r, sort_keys=True) for r in rows}

    extract = {"source": PROBE.name, "anchor": probe["anchor"], "minValidReadings": MIN_VALID,
               "control": probe["control"], "items": {}}
    writes = already = 0
    for pk, (part, stored_expected, tier_name, why) in sorted(PLAN.items()):
        row = by_pk[pk]
        assert row["priceLabel"] == "charter"
        tiers, valid_dates, dropped, zeros = ladder_from(probe["obs"][str(pk)])
        assert len(valid_dates) >= MIN_VALID, f"pk {pk}: {len(valid_dates)} date-valid readings < {MIN_VALID} — re-probe required"
        assert all(t["price"] == t["priceMax"] for t in tiers), f"pk {pk}: tier price moved across dates"
        chosen = [t for t in tiers if t["singular"] == tier_name]
        assert len(chosen) == 1, f"pk {pk}: tier {tier_name!r} not unique in {tiers}"
        chosen = chosen[0]
        # A date-valid reading whose only tier is $0 ("Call to Book") carries no fare
        # (D-575): it is a zero-only date, not a quote. The chosen tier must be
        # quoted non-zero on >= MIN_VALID dates; 613379/613382 have one such date.
        zero_only = [d for d in valid_dates if not probe["obs"][str(pk)][d]["tiers"]]
        assert chosen["datesQuoting"] + len(zero_only) == len(valid_dates), f"pk {pk}: chosen tier absent on a quoting date"
        assert chosen["datesQuoting"] >= MIN_VALID, f"pk {pk}: tier quoted on {chosen['datesQuoting']} dates < {MIN_VALID}"
        new_price = KILLEN_NEW[pk] if part == 2 else stored_expected
        if part == 1:
            assert len(tiers) > 1 and chosen["price"] == stored_expected, f"pk {pk}: stored != chosen tier"
        else:
            assert len(tiers) == 1, f"pk {pk}: not single-tier"
            assert chosen["price"] == new_price and stored_expected not in (chosen["price"],), f"pk {pk}: ruling mismatch"
        extract["items"][str(pk)] = {
            "pk": pk, "name": row["name"], "part": part, "storedBefore": stored_expected,
            "price": new_price, "chosenTier": chosen, "ladder": tiers,
            "justifyingDates": [d for d in valid_dates if d not in zero_only],
            "zeroOnlyDates": zero_only, "discardedDates": dropped,
            "zeroTiersDiscarded": [{"singular": z[0], "note": z[1]} for z in zeros],
            "ruling": why}

        uf = row.get("_unknownFields") or {}
        if float(row["price"]) == new_price and uf.get("priceSource") == SRC:
            already += 1
            continue
        assert float(row["price"]) == stored_expected, f"pk {pk}: stored {row['price']} != expected {stored_expected}"
        print(f"  WRITE part{part} pk={pk} ${row['price']:,.0f} -> ${new_price:,.0f}  {tier_name!r}  {row['name']!r}")
        if part == 2:
            row["price"] = int(new_price)          # Part 1 rows keep #149's price byte-for-byte
        assert isinstance(row["price"], int), f"pk {pk}: price literal must stay an int"
        row["priceConfidence"] = "high"
        uf["priceSource"] = SRC
        uf["priceBasis"] = (f"{why}. Tier {chosen['singular']!r}"
                            + (f" ({chosen['note']})" if chosen["note"] else "")
                            + f" ${new_price:,.0f}, identical on all {chosen['datesQuoting']} date-valid quoting readings"
                            + (f"; {len(zero_only)} date-valid reading(s) carried only a $0 echo, discarded (D-575)" if zero_only else "") + ".")
        uf["boatTiers"] = [f"{t['singular']} ${t['price']:,.0f}" + (f" ({t['note']})" if t["note"] else "")
                           for t in tiers]
        row["_unknownFields"] = uf
        writes += 1

    if args.extract:
        EXTRACT.write_text(json.dumps(extract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  extract -> {EXTRACT.relative_to(REPO)}")

    # Structural assertions on the in-memory result.
    after = {r["pk"]: json.dumps(r, sort_keys=True) for r in rows}
    assert len(rows) == ROWS and list(before) == list(after)
    changed = {pk for pk in before if before[pk] != after[pk]}
    assert changed <= set(PLAN), f"rows outside the plan changed: {changed - set(PLAN)}"
    price_moved = {pk for pk in changed if json.loads(before[pk])["price"] != by_pk[pk]["price"]}
    assert price_moved <= set(KILLEN_NEW), f"price moved outside the Killen 4: {price_moved}"
    print(f"  rows to write: {writes}   already applied: {already}   changed rows: {sorted(changed)}")

    if not args.write:
        print("DRY RUN — not written.")
        return
    if not writes:
        print("0 modified.")
        return
    TOURS.write_text(dump(doc), encoding="utf-8")
    print(f"WROTE tours-data.json ({len(raw)} -> {len(dump(doc))} bytes)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build data/primary.json and data/secondary.json from DfE England CSVs.

Reads:
  england_ks4final.csv  (secondary GCSE)
  england_ks2final.csv  (primary KS2 SATs)

Writes:
  data/secondary.json
  data/primary.json

Run from repo root:
  python3 build_data.py
"""
import csv
import json
import os
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(REPO, "data")

# England national averages (from current index.html SQS formula card).
ENG_A8 = 46.1
ENG_EM = 45.4
ENG_APS = 4.09
ENG_ENT = 40.5

# Greater Manchester LEAs (10).
GM = {
    350: "Bolton", 351: "Bury", 352: "Manchester", 353: "Oldham",
    354: "Rochdale", 355: "Salford", 356: "Stockport", 357: "Tameside",
    358: "Trafford", 359: "Wigan",
}

# Greater London LEAs (33 = City + 32 boroughs).
LONDON = {
    201: "City of London", 202: "Camden", 203: "Greenwich", 204: "Hackney",
    205: "Hammersmith and Fulham", 206: "Islington", 207: "Kensington and Chelsea",
    208: "Lambeth", 209: "Lewisham", 210: "Southwark", 211: "Tower Hamlets",
    212: "Wandsworth", 213: "Westminster",
    301: "Barking and Dagenham", 302: "Barnet", 303: "Bexley", 304: "Brent",
    305: "Bromley", 306: "Croydon", 307: "Ealing", 308: "Enfield", 309: "Haringey",
    310: "Harrow", 311: "Havering", 312: "Hillingdon", 313: "Hounslow",
    314: "Kingston upon Thames", 315: "Merton", 316: "Newham", 317: "Redbridge",
    318: "Richmond upon Thames", 319: "Sutton", 320: "Waltham Forest",
}


def lea_area(lea_code: int, town: str) -> str:
    """Borough name for curated regions, town fallback elsewhere."""
    if lea_code in GM:
        return GM[lea_code]
    if lea_code in LONDON:
        return LONDON[lea_code]
    return town.title() if town else f"LEA {lea_code}"


def lea_region(lea_code: int) -> str:
    if lea_code in GM:
        return "manchester"
    if lea_code in LONDON:
        return "london"
    return "other"


def parse_num(v):
    """Strip %, treat suppression markers as None."""
    if v is None:
        return None
    v = v.strip()
    if v in ("", "SUPP", "NE", "NP", "..", "LOWCOV", "N/A", "NA", "NR", "x"):
        return None
    v = v.rstrip("%")
    try:
        return float(v)
    except ValueError:
        return None


def is_priv(nftype: str) -> bool:
    return nftype in {"IND", "INDSS", "NMSS"}


def religious_tag(reldenom: str) -> str | None:
    r = reldenom or ""
    if "Roman Catholic" in r or "Catholic" in r:
        return "RC"
    if "Church of England" in r or "Anglican" in r:
        return "CofE"
    if "Jewish" in r:
        return "Jewish"
    if "Islam" in r or "Muslim" in r:
        return "Muslim"
    if "Hindu" in r:
        return "Hindu"
    if "Sikh" in r:
        return "Sikh"
    if "Methodist" in r:
        return "Methodist"
    if "Quaker" in r:
        return "Quaker"
    return None


def classify_secondary(row) -> str:
    admpol = row.get("ADMPOL", "")
    nftype = row.get("NFTYPE", "")
    egender = row.get("EGENDER", "")

    if admpol == "SEL":
        base = "Grammar"
    elif is_priv(nftype):
        base = "Independent"
    elif nftype == "CTC":
        base = "City Technology College"
    elif nftype == "UTC":
        base = "UTC"
    else:
        base = "Non-selective"

    parts = [base]
    if egender == "BOYS":
        parts.append("Boys")
    elif egender == "GIRLS":
        parts.append("Girls")

    label = " · ".join(parts)
    tag = religious_tag(row.get("RELDENOM", ""))
    if tag:
        label += f" ({tag})"
    return label


def classify_primary(row) -> str:
    nftype = row.get("NFTYPE", "")
    base_map = {
        "AC": "Academy", "ACC": "Academy", "ACCS": "Academy", "ACS": "Academy",
        "F": "Free School", "FS": "Free School", "FD": "Foundation", "FDS": "Foundation",
        "VA": "Voluntary Aided", "VC": "Voluntary Controlled",
        "CY": "Community", "CYS": "Community",
    }
    base = base_map.get(nftype, "State")
    tag = religious_tag(row.get("RELDENOM", ""))
    if tag:
        base += f" ({tag})"
    return base


def percentile_ranks(values):
    """Return parallel list of percentiles (0–100) using midrank for ties.

    Ties get the average of the ranks they would occupy (standard percentile-
    rank convention used by DfE-style ranking). p = 100 * midrank / n.
    """
    n = len(values)
    indexed = sorted(range(n), key=lambda i: values[i])
    pct = [0.0] * n
    i = 0
    while i < n:
        j = i
        # Walk forward while values are tied.
        v = values[indexed[i]]
        while j + 1 < n and values[indexed[j + 1]] == v:
            j += 1
        # Ranks i..j (1-based: i+1 .. j+1). Midrank = average.
        mid = ((i + 1) + (j + 1)) / 2.0
        p = 100.0 * mid / n
        for k in range(i, j + 1):
            pct[indexed[k]] = p
        i = j + 1
    return pct


def build_secondary():
    src = os.path.join(REPO, "england_ks4final.csv")
    rows = []
    with open(src, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("RECTYPE") != "1":
                continue
            a8 = parse_num(row.get("ATT8SCR"))
            em = parse_num(row.get("PTL2BASICS_95"))
            aps = parse_num(row.get("EBACCAPS"))
            ent = parse_num(row.get("PTEBACC_E_PTQ_EE"))
            if None in (a8, em, aps, ent):
                continue
            lea = int(row["LEA"])
            rec = {
                "name": row["SCHNAME"].strip(),
                "area": lea_area(lea, row.get("TOWN", "")),
                "type": classify_secondary(row),
                "lea": lea,
                "region": lea_region(lea),
                "a8": round(a8, 1),
                "em": round(em, 1),
                "aps": round(aps, 2),
                "ent": round(ent, 1),
            }
            if is_priv(row.get("NFTYPE", "")):
                rec["priv"] = True
            rows.append(rec)
    return rows


def build_primary():
    src = os.path.join(REPO, "england_ks2final.csv")
    rows = []
    with open(src, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("RECTYPE") != "1":
                continue
            rwm = parse_num(row.get("PTRWM_EXP"))
            hs = parse_num(row.get("PTRWM_HIGH"))
            read = parse_num(row.get("READ_AVERAGE"))
            maths = parse_num(row.get("MAT_AVERAGE"))
            if None in (rwm, hs, read, maths):
                continue
            lea = int(row["LEA"])
            rows.append({
                "name": row["SCHNAME"].strip(),
                "area": lea_area(lea, row.get("TOWN", "")),
                "type": classify_primary(row),
                "lea": lea,
                "region": lea_region(lea),
                "rwm": round(rwm, 1),
                "hs": round(hs, 1),
                "read": round(read, 1),
                "maths": round(maths, 1),
            })

    # National percentiles across the full mainstream set.
    pe = percentile_ranks([r["rwm"] for r in rows])
    ph = percentile_ranks([r["hs"] for r in rows])
    pr = percentile_ranks([r["read"] for r in rows])
    pm = percentile_ranks([r["maths"] for r in rows])
    for i, r in enumerate(rows):
        r["pe"] = round(pe[i], 1)
        r["ph"] = round(ph[i], 1)
        r["pr"] = round(pr[i], 1)
        r["pm"] = round(pm[i], 1)

    # 11+ Readiness: min-max within each LA on hs, read, maths.
    by_lea = defaultdict(list)
    for i, r in enumerate(rows):
        by_lea[r["lea"]].append(i)

    for lea, idxs in by_lea.items():
        if len(idxs) < 3:
            for i in idxs:
                rows[i]["lh"] = None
                rows[i]["lr"] = None
                rows[i]["lm"] = None
            continue
        for field, key in (("hs", "lh"), ("read", "lr"), ("maths", "lm")):
            vals = [rows[i][field] for i in idxs]
            lo, hi = min(vals), max(vals)
            span = hi - lo
            for i in idxs:
                if span == 0:
                    rows[i][key] = 50.0
                else:
                    rows[i][key] = round(100 * (rows[i][field] - lo) / span, 1)
    return rows


def inject_into_html(sec_json: str, pri_json: str):
    """Splice the JSON payloads into index.html between marker comments."""
    html_path = os.path.join(REPO, "index.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    def splice(label: str, payload: str) -> None:
        nonlocal html
        begin = f"<!-- BEGIN-DATA-{label} -->"
        end = f"<!-- END-DATA-{label} -->"
        block = (
            f'{begin}\n'
            f'<script type="application/json" id="data-{label.lower()}">{payload}</script>\n'
            f'{end}'
        )
        bi = html.find(begin)
        ei = html.find(end)
        if bi == -1 or ei == -1:
            raise RuntimeError(f"Markers {begin}/{end} not found in index.html")
        html = html[:bi] + block + html[ei + len(end):]

    splice("SECONDARY", sec_json)
    splice("PRIMARY", pri_json)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Building secondary…", file=sys.stderr)
    sec = build_secondary()
    print(f"  {len(sec)} secondary schools", file=sys.stderr)

    print("Building primary…", file=sys.stderr)
    pri = build_primary()
    print(f"  {len(pri)} primary schools", file=sys.stderr)

    sec_json = json.dumps(sec, separators=(",", ":"), ensure_ascii=False)
    pri_json = json.dumps(pri, separators=(",", ":"), ensure_ascii=False)

    # Debug artifacts (also useful for diffing data changes between runs).
    with open(os.path.join(OUT_DIR, "secondary.json"), "w", encoding="utf-8") as f:
        f.write(sec_json)
    with open(os.path.join(OUT_DIR, "primary.json"), "w", encoding="utf-8") as f:
        f.write(pri_json)

    # Inline into the page so it works standalone (no fetch needed).
    inject_into_html(sec_json, pri_json)

    print(
        f"Wrote {OUT_DIR}/secondary.json, {OUT_DIR}/primary.json, "
        f"and injected into index.html",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

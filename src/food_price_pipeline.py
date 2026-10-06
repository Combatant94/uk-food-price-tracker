"""
UK Food Price Tracker, 2021-2026
Reproducible pipeline: reads three public ONS files and writes summary tables
and the dashboard data file.

Inputs (download from ons.gov.uk, place in data/):
  mm23.csv                      - Consumer price inflation time series (CPI indices and weights)
  upload-pricequotes202101.csv  - CPI price quotes, January 2021
  upload-pricequotes202501.csv  - CPI price quotes, January 2025
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "reports"
OUT.mkdir(exist_ok=True)

CLASSES = {
    "01.1.1": "Bread & cereals", "01.1.2": "Meat", "01.1.3": "Fish",
    "01.1.4": "Milk, cheese & eggs", "01.1.5": "Oils & fats", "01.1.6": "Fruit",
    "01.1.7": "Vegetables", "01.1.8": "Sugar, jam & confectionery",
    "01.1.9": "Other food products", "01.2.1": "Coffee, tea & cocoa",
    "01.2.2": "Water, soft drinks & juices",
}
# ONS price quotes glossary. Region 1 = head-office catalogue collections (excluded).
REGIONS = {2: "London", 3: "South East", 4: "South West", 5: "East Anglia", 6: "East Midlands",
           7: "West Midlands", 8: "Yorkshire & Humber", 9: "North West", 10: "North",
           11: "Wales", 12: "Scotland", 13: "Northern Ireland"}
START = "2021-01-01"


# ------------------------------------------------------------------ 1. MM23 category indices
def find_col(columns, prefix, code):
    pat = re.compile(rf"^{prefix} {re.escape(code)}\s*:")
    hits = [c for c in columns if pat.match(c)]
    if len(hits) != 1:
        raise ValueError(f"Expected one column for {prefix} {code}, found {hits}")
    return hits[0]


def load_mm23():
    mm = pd.read_csv(DATA / "mm23.csv", low_memory=False).set_index("Title")
    monthly = [i for i in mm.index if re.fullmatch(r"\d{4} [A-Z]{3}", str(i))]
    yearly = [i for i in mm.index if re.fullmatch(r"\d{4}", str(i))]
    M = mm.loc[monthly]
    M.index = pd.to_datetime(M.index, format="%Y %b")
    idx, wts = {}, {}
    for code, name in CLASSES.items():
        idx[name] = pd.to_numeric(M[find_col(mm.columns, "CPI INDEX", code)], errors="coerce")
        w = pd.to_numeric(mm.loc[yearly, find_col(mm.columns, "CPI WEIGHTS", code)], errors="coerce")
        w.index = w.index.astype(int)
        wts[name] = w
    idx["Food & non-alcoholic drinks"] = pd.to_numeric(M[find_col(mm.columns, "CPI INDEX", "01")], errors="coerce")
    idx["All CPI items"] = pd.to_numeric(M["CPI INDEX 00: ALL ITEMS 2015=100"], errors="coerce")
    w01 = pd.to_numeric(mm.loc[yearly, find_col(mm.columns, "CPI WEIGHTS", "01")], errors="coerce")
    w01.index = w01.index.astype(int)
    I = pd.DataFrame(idx).loc["2019-01-01":].dropna(how="all")
    return I, pd.DataFrame(wts), w01


def category_analysis(I, W, w01):
    yoy = (I / I.shift(12) - 1) * 100
    latest = I.index.max()
    cum = ((I.loc[latest] / I.loc[START] - 1) * 100).sort_values(ascending=False)
    # Contribution of each class to the food & non-alcoholic drinks annual rate:
    # (class weight / division weight) x class annual rate, using that year's weights.
    rows = {}
    for t in yoy.index:
        if t.year in W.index and t.year in w01.index:
            rows[t] = W.loc[t.year] / w01.loc[t.year] * yoy.loc[t, list(CLASSES.values())]
    C = pd.DataFrame(rows).T
    check = (C.sum(axis=1) - yoy["Food & non-alcoholic drinks"]).loc[START:].abs()
    return yoy, cum, C, latest, check


# ------------------------------------------------------------------ 2. Price quotes (matched shops)
def load_quotes(name):
    d = pd.read_csv(DATA / name)
    d.columns = d.columns.str.strip()
    # Food items (ITEM_ID 21xxxx); valid, priced quotes only (validity 3/4; price 0 = no price collected)
    return d[d.ITEM_ID.between(210000, 219999) & d.VALIDITY.isin([3, 4]) & (d.PRICE > 0)]


def matched_pairs(a, b):
    """Same item, same shop, same region in both years, so like is compared with like."""
    key = ["ITEM_ID", "REGION", "SHOP_CODE"]
    A = (a.groupby(key).agg(p21=("PRICE", "mean"), desc=("ITEM_DESC", "first"),
                            shop_type=("SHOP_TYPE", "first")).reset_index())
    B = b.groupby(key).agg(p25=("PRICE", "mean"), desc25=("ITEM_DESC", "first")).reset_index()
    P = A.merge(B, on=key)
    P["rel"] = P.p25 / P.p21
    return P[(P.rel > 0.2) & (P.rel < 5)]  # drop implausible matches (product or unit changed)


def geo_change(r):
    return (np.exp(np.log(r).mean()) - 1) * 100


def quotes_analysis():
    a = load_quotes("upload-pricequotes202101.csv")
    b = load_quotes("upload-pricequotes202501.csv")
    # Naive comparison (different shops each year), kept only to show why matching matters
    naive = (b.groupby("ITEM_ID").PRICE.median() / a.groupby("ITEM_ID").PRICE.median() - 1) * 100
    P = matched_pairs(a, b)
    items = P.groupby("ITEM_ID").agg(item=("desc25", "first"), pairs=("rel", "size"),
                                     p21=("p21", "median"), p25=("p25", "median"),
                                     change=("rel", geo_change))
    items = items[items.pairs >= 20]
    items["naive_change"] = naive.reindex(items.index)

    # Regions: like-for-like basket of items priced in all 12 regions
    R = P[P.REGION.isin(REGIONS)]
    ir = R.groupby(["REGION", "ITEM_ID"]).rel.agg(n="size", lr=lambda r: np.log(r).mean()).reset_index()
    ir = ir[ir.n >= 3]
    common = ir.groupby("ITEM_ID").REGION.nunique().loc[lambda s: s == len(REGIONS)].index
    region = (ir[ir.ITEM_ID.isin(common)].groupby("REGION").lr.mean()
              .apply(lambda x: (np.exp(x) - 1) * 100).rename(index=REGIONS).sort_values(ascending=False))

    # Shop type: multiples (1) vs independents (2), items with >=5 matched pairs in both
    S = P[P.shop_type.isin([1, 2])]
    st = S.groupby(["ITEM_ID", "shop_type"]).agg(n=("rel", "size"), lr=("rel", lambda r: np.log(r).mean()),
                                                 p21=("p21", "median"), p25=("p25", "median")).reset_index()
    st = st[st.n >= 5]
    both = st.groupby("ITEM_ID").shop_type.nunique().loc[lambda s: s == 2].index
    st = st[st.ITEM_ID.isin(both)]
    shop_change = st.groupby("shop_type").lr.mean().apply(lambda x: (np.exp(x) - 1) * 100)
    lv = st.pivot(index="ITEM_ID", columns="shop_type", values=["p21", "p25"])
    premium = {y: (np.exp(np.log(lv[f"p{y}"][2] / lv[f"p{y}"][1]).mean()) - 1) * 100 for y in ("21", "25")}
    return a, b, P, items, region, len(common), shop_change, premium, len(both), int((S.shop_type == 2).sum())


def main():
    I, W, w01 = load_mm23()
    yoy, cum, C, latest, check = category_analysis(I, W, w01)
    a, b, P, items, region, n_common, shop_change, premium, n_shop_items, n_indep = quotes_analysis()
    food = I["Food & non-alcoholic drinks"]
    ons_jan21_jan25 = (food["2025-01-01"] / food["2021-01-01"] - 1) * 100
    peak = yoy["Food & non-alcoholic drinks"].loc[START:].idxmax()

    summary = {
        "latest_month": latest.strftime("%b %Y"),
        "food_cum_since_2021": round(cum["Food & non-alcoholic drinks"], 1),
        "cpi_cum_since_2021": round(cum["All CPI items"], 1),
        "food_peak_month": peak.strftime("%b %Y"),
        "food_peak_rate": round(yoy.loc[peak, "Food & non-alcoholic drinks"], 1),
        "food_latest_rate": round(yoy.loc[latest, "Food & non-alcoholic drinks"], 1),
        "cpi_latest_rate": round(yoy.loc[latest, "All CPI items"], 1),
        "contribution_check_mean_abs_pp": round(check.mean(), 2),
        "valid_food_quotes": [int(len(a)), int(len(b))],
        "matched_pairs": int(len(P)), "items_compared": int(len(items)),
        "median_item_change_matched": round(items.change.median(), 1),
        "ons_food_change_jan21_jan25": round(ons_jan21_jan25, 1),
        "regional_items": int(n_common),
        "shop_items": int(n_shop_items), "independent_pairs": n_indep,
        "multiples_change": round(shop_change[1], 1), "independents_change": round(shop_change[2], 1),
        "independent_premium_2021": round(premium["21"], 1),
        "independent_premium_2025": round(premium["25"], 1),
    }
    s = yoy.loc[START:]
    dash = {
        "summary": summary,
        "monthly": {"labels": [d.strftime("%b %Y") for d in s.index],
                    "food": s["Food & non-alcoholic drinks"].round(1).tolist(),
                    "cpi": s["All CPI items"].round(1).tolist()},
        "categories": [{"name": k, "cum": round(v, 1), "peak_contrib": round(C.loc[peak, k], 2),
                        "latest_rate": round(yoy.loc[latest, k], 1)}
                       for k, v in cum.items() if k in CLASSES.values()],
        "contrib": {"labels": [d.strftime("%b %Y") for d in C.loc[START:].index],
                    "series": {k: C.loc[START:, k].round(2).tolist() for k in CLASSES.values()}},
        "items": [{"item": r.item.title(), "p21": round(r.p21, 2), "p25": round(r.p25, 2),
                   "change": round(r.change, 1), "naive": round(r.naive_change, 1), "pairs": int(r.pairs)}
                  for r in items.sort_values("change", ascending=False).itertuples()],
        "regions": [{"region": k, "change": round(v, 1)} for k, v in region.items()],
    }
    (OUT / "dashboard_data.json").write_text(json.dumps(dash))
    cum.round(1).to_csv(OUT / "category_cumulative_change.csv", header=["pct_change_jan2021_to_latest"])
    items.round(2).to_csv(OUT / "item_price_change_matched.csv")
    region.round(1).to_csv(OUT / "regional_change.csv", header=["pct_change_jan2021_jan2025"])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

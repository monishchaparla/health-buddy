"""Build data/foods.json from the Indian Nutrient Databank, USDA basics and our alias list.

INDB has no licence file, so we never commit it: this script downloads INDB.xlsx into
data/raw/ (git-ignored) and writes data/foods.json (git-ignored). USDA SR Legacy is public
domain (CC0), so the small extract data/usda_basics.csv is committed; rebuild it with --usda
after downloading the SR Legacy CSV zip into data/raw/.

python -m healthbuddy.foods_build          # build foods.json (downloads INDB if missing)
python -m healthbuddy.foods_build --usda   # rebuild data/usda_basics.csv from SR Legacy
"""

from __future__ import annotations

import csv
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import openpyxl

DATA = Path(__file__).resolve().parents[1] / "data"
RAW = DATA / "raw"
INDB_URL = "https://raw.githubusercontent.com/lindsayjaacks/Indian-Nutrient-Databank-INDB-/main/INDB.xlsx"
SR_ZIP = RAW / "sr_legacy.zip"  # https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip

# (fdc_id, key, portion label shown to users, substring of the USDA portion description to use)
USDA_PICKS = [
    (173944, "banana", "piece", "medium"),
    (171688, "apple", "piece", "medium"),
    (169910, "mango", "cup", "cup pieces"),
    (173044, "guava", "piece", "fruit, without refuse"),
    (169926, "papaya", "cup", "cup 1\" pieces"),
    (169097, "orange", "piece", "fruit (2-5/8\" dia)"),
    (167765, "watermelon", "wedge", "wedge"),
    (169134, "pomegranate", "cup", "cup arils"),
    (174683, "grapes", "cup", "cup"),
    (167759, "sapota", "piece", "sapodilla"),
    (168191, "dates", "piece", "date, pitted"),
    (171265, "milk", "cup", "cup"),
    (171284, "curd", "cup", "cup (8 fl oz)"),
    (170874, "buttermilk_cultured", "cup", "cup"),
    (173412, "ghee", "tbsp", "tbsp"),
    (173430, "butter", "tbsp", "tbsp"),
    (169655, "sugar", "tsp", "tsp"),
    (169640, "honey", "tbsp", "tbsp"),
    (173806, "peanuts", "handful", "oz"),
    (170567, "almonds", "handful", "oz (23 whole kernels)"),
    (170162, "cashews", "handful", "oz"),
    (168409, "cucumber", "cup", "cup slices"),
    (170457, "tomato", "piece", "medium whole"),
    (170000, "onion", "piece", "medium"),
    (170393, "carrot", "piece", "medium"),
    (174924, "white_bread", "slice", "slice"),
    (172688, "brown_bread", "slice", "slice"),
    (173904, "oats", "cup", "cup"),
    (170174, "coconut_water", "cup", "cup"),
    (171477, "chicken_breast", "piece", "breast, bone and skin removed"),
    (168878, "white_rice_cooked", "cup", "cup"),
    (173227, "black_tea", "cup", "cup"),
    (171890, "black_coffee", "cup", "cup"),
]
NUTRIENTS = {"1008": "kcal", "1003": "protein", "1005": "carbs", "1004": "fat", "1079": "fibre"}


def build_usda() -> None:
    picks = {str(f): (k, label, sub) for f, k, label, sub in USDA_PICKS}
    with zipfile.ZipFile(SR_ZIP) as z:
        prefix = next(n for n in z.namelist() if n.endswith("food.csv")).rsplit("/", 1)[0] + "/"

        def rows(name):
            with z.open(prefix + name) as f:
                yield from csv.DictReader(line.decode("utf-8") for line in f)

        names = {r["fdc_id"]: r["description"] for r in rows("food.csv") if r["fdc_id"] in picks}
        nut: dict[str, dict] = {f: {} for f in picks}
        for r in rows("food_nutrient.csv"):
            if r["fdc_id"] in picks and r["nutrient_id"] in NUTRIENTS:
                nut[r["fdc_id"]][NUTRIENTS[r["nutrient_id"]]] = float(r["amount"])
        portions: dict[str, tuple[str, float]] = {}
        for r in rows("food_portion.csv"):
            f = r["fdc_id"]
            if f in picks and f not in portions and picks[f][2].lower() in (r["portion_description"] or r["modifier"]).lower():
                portions[f] = ((r["portion_description"] or r["modifier"]), float(r["gram_weight"]) / float(r["amount"] or 1))
    out = DATA / "usda_basics.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "fdc_id", "description", "kcal", "protein", "carbs", "fat", "fibre", "unit", "unit_g", "usda_portion"])
        for fdc, (key, label, _) in picks.items():
            if fdc not in portions:
                raise SystemExit(f"No matching portion for {fdc} {names.get(fdc)}")
            n = nut[fdc]
            w.writerow([key, fdc, names[fdc], *(n.get(k, 0.0) for k in NUTRIENTS.values()), label, round(portions[fdc][1], 1), portions[fdc][0]])
    print(f"wrote {out}")


def load_indb() -> dict[str, dict]:
    path = RAW / "INDB.xlsx"
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        print(f"downloading {INDB_URL}")
        urllib.request.urlretrieve(INDB_URL, path)
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = next(it)
    foods = {}
    for row in it:
        d = dict(zip(header, row))
        if not d["food_code"] or d["energy_kcal"] is None:
            continue
        kcal = float(d["energy_kcal"])
        serving_kcal = d["unit_serving_energy_kcal"]
        unit_g = round(float(serving_kcal) / kcal * 100, 1) if kcal and serving_kcal else 100.0
        foods[d["food_code"]] = {
            "name": d["food_name"].strip(),
            "unit": (d["servings_unit"] or "").strip() or "serving",
            "unit_g": unit_g,
            "per100": {k: round(float(d[c] or 0), 2) for k, c in
                       [("kcal", "energy_kcal"), ("protein", "protein_g"), ("carbs", "carb_g"), ("fat", "fat_g"), ("fibre", "fibre_g")]},
        }
    return foods


def build() -> list[dict]:
    indb = load_indb()
    usda = {}
    with (DATA / "usda_basics.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            usda[r["key"]] = {"name": r["description"], "unit": r["unit"], "unit_g": float(r["unit_g"]),
                              "per100": {k: float(r[k]) for k in ("kcal", "protein", "carbs", "fat", "fibre")}}
    out: list[dict] = []
    curated_codes = set()
    with (DATA / "food_aliases.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            src = indb[r["code"]] if r["source"] == "indb" else usda[r["code"]]
            if r["source"] == "indb" and r["approx"] != "1":
                curated_codes.add(r["code"])
            out.append({
                "id": r["key"],
                "name": r["name_en"],
                "name_te": r["name_te"],
                "aliases": [a.strip() for a in r["aliases"].split("|") if a.strip()],
                "source": "INDB" if r["source"] == "indb" else "USDA SR Legacy",
                "source_ref": f"{r['code']} {src['name']}",
                "unit": r["unit"] or src["unit"],
                "unit_g": float(r["unit_g"]) if r["unit_g"] else src["unit_g"],
                "per100": src["per100"],
                "approx_of": src["name"] if r["approx"] == "1" else None,
                "note": r["note"] or None,
            })
    # Every other INDB recipe stays searchable by its English name.
    for code, d in indb.items():
        if code not in curated_codes:
            out.append({"id": f"indb:{code}", "name": d["name"], "name_te": "", "aliases": [], "source": "INDB",
                        "source_ref": f"{code} {d['name']}", "unit": d["unit"], "unit_g": d["unit_g"],
                        "per100": d["per100"], "approx_of": None, "note": None})
    ids = [f["id"] for f in out]
    assert len(ids) == len(set(ids)), "duplicate food ids"
    (DATA / "foods.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"wrote {len(out)} foods to {DATA / 'foods.json'}")
    return out


if __name__ == "__main__":
    build_usda() if "--usda" in sys.argv else build()

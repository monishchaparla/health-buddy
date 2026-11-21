"""Open Food Facts barcode lookup (data under ODbL; we cache single products, never bulk-copy)."""

from __future__ import annotations

import json
import re
import sqlite3

import httpx

URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
FIELDS = "product_name,brands,nutriments,serving_quantity,serving_size,quantity"
HEADERS = {"User-Agent": "TejuHealthAI/0.1"}


class NotFound(LookupError):
    pass


def valid(code: str) -> bool:
    return bool(re.fullmatch(r"\d{8,14}", code))


def to_food(code: str, p: dict) -> dict:
    n = p.get("nutriments") or {}
    kcal = n.get("energy-kcal_100g")
    if kcal is None and n.get("energy_100g") is not None:
        kcal = float(n["energy_100g"]) / 4.184  # energy_100g is kJ
    if kcal is None:
        raise NotFound("This product has no nutrition facts on Open Food Facts yet.")
    serving = p.get("serving_quantity")
    try:
        serving = float(serving) if serving else None
    except (TypeError, ValueError):
        serving = None
    name = " ".join(x for x in [p.get("brands", "").split(",")[0].strip(), p.get("product_name", "").strip()] if x) or code
    return {
        "id": f"off:{code}", "name": name, "name_te": "", "source": "Open Food Facts",
        "unit": "serving" if serving else "100 g", "unit_g": serving or 100.0,
        "per100": {"kcal": round(float(kcal), 1), "protein": float(n.get("proteins_100g") or 0),
                   "carbs": float(n.get("carbohydrates_100g") or 0), "fat": float(n.get("fat_100g") or 0),
                   "fibre": float(n.get("fiber_100g") or 0)},
        "approx_of": None, "note": None, "serving_size": p.get("serving_size"),
    }


def lookup(conn: sqlite3.Connection, code: str, client: httpx.Client | None = None) -> dict:
    row = conn.execute("SELECT payload FROM barcode_cache WHERE code = ?", (code,)).fetchone()
    if row:
        return json.loads(row["payload"])
    client = client or httpx.Client(timeout=8, headers=HEADERS)
    r = client.get(URL.format(code=code), params={"fields": FIELDS})
    if r.status_code == 404 or (r.status_code == 200 and r.json().get("status") == 0):
        raise NotFound("No product with this barcode on Open Food Facts.")
    r.raise_for_status()
    food = to_food(code, r.json()["product"])
    conn.execute("INSERT OR REPLACE INTO barcode_cache (code, payload) VALUES (?, ?)", (code, json.dumps(food)))
    return food

"""Food lookup: exact alias match, then substring, then fuzzy, over English, Telugu and Romanised names."""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

FOODS_JSON = Path(__file__).resolve().parents[1] / "data" / "foods.json"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower()
    # Drop punctuation and symbols only; a regex \w would also drop Telugu vowel signs (Mn/Mc).
    s = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in s)
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=1)
def _load():
    if not FOODS_JSON.exists():
        raise RuntimeError("data/foods.json is missing. Run: python -m healthbuddy.foods_build")
    foods = json.loads(FOODS_JSON.read_text(encoding="utf-8"))
    by_id = {f["id"]: f for f in foods}
    names: dict[str, str] = {}  # normalised name -> food id; curated foods come first in foods.json so they win
    for f in foods:
        for n in [f["name"], f["name_te"], *f["aliases"]]:
            k = norm(n)
            if k and k not in names:
                names[k] = f["id"]
    curated = [k for k, fid in names.items() if not fid.startswith("indb:")]
    return foods, by_id, names, curated


def get(food_id: str) -> dict | None:
    return _load()[1].get(food_id)


def resolve(name: str) -> dict | None:
    """Best single match for a dish name, or None. Used for parsed meal items."""
    _, by_id, names, curated = _load()
    q = norm(name)
    if not q:
        return None
    if q in names:
        return by_id[names[q]]
    # Plural or extra words: "idlis", "plain idli with ghee" -> try dropping a trailing s, then whole-word containment.
    if q.endswith("s") and q[:-1] in names:
        return by_id[names[q[:-1]]]
    words = f" {q} "
    hits = [k for k in curated if f" {k} " in words]
    if hits:
        return by_id[names[max(hits, key=len)]]
    close = difflib.get_close_matches(q, curated, n=1, cutoff=0.82) or difflib.get_close_matches(q, list(names), n=1, cutoff=0.88)
    return by_id[names[close[0]]] if close else None


def segment(words: list[str]) -> list[tuple[str, dict]]:
    """Split 'idli sambar chutney' into known dishes by longest exact name match, left to right."""
    _, by_id, names, _ = _load()
    out, i = [], 0
    while i < len(words):
        for j in range(len(words), i, -1):
            k = " ".join(words[i:j])
            if k in names or (k.endswith("s") and k[:-1] in names):
                out.append((k, by_id[names.get(k) or names[k[:-1]]]))
                i = j
                break
        else:
            i += 1
    return out


def search(query: str, limit: int = 20) -> list[dict]:
    foods, by_id, names, _ = _load()
    q = norm(query)
    if not q:
        return [f for f in foods if not f["id"].startswith("indb:")][:limit]
    scored: dict[str, float] = {}
    for k, fid in names.items():
        if k == q:
            s = 3.0
        elif k.startswith(q):
            s = 2.0
        elif q in k:
            s = 1.5
        else:
            continue
        s += 0.5 if not fid.startswith("indb:") else 0  # curated dishes first
        scored[fid] = max(scored.get(fid, 0), s)
    if len(scored) < limit:
        for k in difflib.get_close_matches(q, list(names), n=limit, cutoff=0.7):
            scored.setdefault(names[k], 1.0)
    ranked = sorted(scored, key=lambda fid: (-scored[fid], by_id[fid]["name"]))
    return [by_id[fid] for fid in ranked[:limit]]

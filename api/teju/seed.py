"""Dev seeder: a demo family with 14 days of meals and sample Health Connect data.

All values are synthetic and stored with source 'seed', so the UI labels them as sample data.
Health data goes through the same upsert as POST /sync/health-connect.

python -m teju.seed            # creates or resets the demo account
Demo login: DEMO_EMAIL / DEMO_PASSWORD from the environment, defaults below (local dev only).
"""

from __future__ import annotations

import os
import random
from datetime import date, datetime, timedelta, timezone

from teju import auth, db, foods, nutrition
from teju.api import HealthRecordIn, SyncIn, upsert_health

DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "teju-demo-2026")
IST = timezone(timedelta(hours=5, minutes=30))

FAMILY = [
    dict(name="Lakshmi", relation="self", is_self=1, sex="female", dob="1984-03-12", height_cm=158, weight_kg=64, activity="light", goal="maintain"),
    dict(name="Ravi", relation="spouse", sex="male", dob="1980-08-02", height_cm=171, weight_kg=82, activity="sedentary", goal="lose"),
    dict(name="Ammamma", relation="grandparent", sex="female", dob="1953-01-20", height_cm=150, weight_kg=52, activity="sedentary", goal="maintain"),
    dict(name="Chinni", relation="child", sex="female", dob="2015-06-15", height_cm=132, weight_kg=28, activity="active", goal="maintain"),
]
# (slot, [(food_id, quantity, unit)]) options per slot; one is picked per day
MENU = {
    "breakfast": [[("idli", 4, ""), ("sambar", 1, ""), ("coconut_chutney", 2, "")],
                  [("pesarattu", 3, ""), ("upma", 1, ""), ("tomato_chutney", 2, "")],
                  [("plain_dosa", 3, ""), ("peanut_chutney", 2, "")],
                  [("poha", 2, ""), ("tea", 1, "")],
                  [("upma", 2, ""), ("coffee", 1, "")]],
    "lunch": [[("rice", 1, ""), ("pappu", 1, ""), ("bhindi_fry", 1, ""), ("curd", 1, "")],
              [("rice", 1, ""), ("sambar", 1, ""), ("cabbage_curry", 1, ""), ("buttermilk", 1, "glass")],
              [("pulihora", 1, ""), ("curd", 1, ""), ("gongura_pachadi", 1, "")],
              [("chapati", 3, ""), ("chicken_curry", 1, ""), ("raita", 1, "")],
              [("rice", 1, ""), ("fish_curry", 1, ""), ("beans_curry", 1, "")]],
    "snack": [[("tea", 1, ""), ("murmura", 1, "")], [("banana", 1, "")], [("coffee", 1, ""), ("peanut_chikki", 2, "")],
              [("guava", 1, "")], [("sprouts", 1, "")]],
    "dinner": [[("chapati", 3, ""), ("dal", 1, "")], [("rice", 1, ""), ("rasam", 1, ""), ("aloo_curry", 1, "")],
               [("curd_rice", 1, "")], [("plain_dosa", 3, ""), ("sambar", 1, "")], [("chapati", 2, ""), ("palak_paneer", 1, "")]],
}
PORTION = {"Lakshmi": 0.9, "Ravi": 1.25, "Ammamma": 0.7, "Chinni": 0.6}


def reset_demo(conn) -> int:
    conn.execute("DELETE FROM users WHERE email = ?", (DEMO_EMAIL,))
    cur = conn.execute("INSERT INTO users (email, pw_hash, name, lang, consent_at) VALUES (?, ?, ?, 'en', ?)",
                       (DEMO_EMAIL, auth.hash_password(DEMO_PASSWORD), "Lakshmi", datetime.now(timezone.utc).isoformat()))
    return cur.lastrowid


def seed(days: int = 14, today: date | None = None) -> None:
    db.init()
    today = today or date.today()
    rng = random.Random(7)
    with db.connect() as conn:
        uid = reset_demo(conn)
        for m in FAMILY:
            consent = datetime.now(timezone.utc).isoformat() if m["relation"] == "child" else None
            cur = conn.execute(
                """INSERT INTO members (user_id, name, relation, is_self, sex, dob, height_cm, weight_kg, activity, goal, parental_consent_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (uid, m["name"], m["relation"], m.get("is_self", 0), m["sex"], m["dob"], m["height_cm"], m["weight_kg"],
                 m["activity"], m["goal"], consent))
            mid = cur.lastrowid
            records = []
            for d in range(days):
                day = today - timedelta(days=d)
                for slot, options in MENU.items():
                    if d == 0 and slot == "dinner":
                        continue  # today is still in progress
                    if slot == "snack" and rng.random() < 0.3:
                        continue
                    meal = conn.execute("INSERT INTO meals (member_id, eaten_on, slot, source) VALUES (?, ?, ?, ?)",
                                        (mid, day.isoformat(), slot, rng.choice(["text", "search", "photo"]))).lastrowid
                    for food_id, qty, unit in rng.choice(options):
                        f = foods.get(food_id)
                        q = round(qty * PORTION[m["name"]], 1)
                        grams = nutrition.grams_for(f, q, unit)
                        n = nutrition.nutrients(f["per100"], grams)
                        conn.execute(
                            """INSERT INTO meal_items (meal_id, food_id, name, quantity, unit, grams, kcal, protein, carbs, fat, fibre, source, approx_of, note)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (meal, f["id"], f["name"], q, unit or f["unit"], round(grams, 1), *(n[k] for k in nutrition.KEYS),
                             f["source"], f.get("approx_of"), f.get("note")))
                # Health Connect style records: one steps and active-calories record per day, a sleep session, HR samples.
                base = {"Lakshmi": 6500, "Ravi": 4200, "Ammamma": 2600, "Chinni": 9000}[m["name"]]
                start = datetime(day.year, day.month, day.day, 6, 0, tzinfo=IST)
                steps = max(500, int(rng.gauss(base, base * 0.25)))
                records += [
                    HealthRecordIn(id=f"seed-{mid}-{day}-steps", type="steps", start=start, end=start + timedelta(hours=16), value=steps, unit="count"),
                    HealthRecordIn(id=f"seed-{mid}-{day}-kcal", type="active_kcal", start=start, end=start + timedelta(hours=16), value=round(steps * 0.04), unit="kcal"),
                ]
                sleep_min = int(rng.gauss({"Chinni": 590, "Ravi": 385}.get(m["name"], 420), 35))
                wake = datetime(day.year, day.month, day.day, 6, 15, tzinfo=IST)
                records.append(HealthRecordIn(id=f"seed-{mid}-{day}-sleep", type="sleep", start=wake - timedelta(minutes=sleep_min), end=wake, value=sleep_min, unit="min"))
                for h in (7, 10, 13, 16, 19, 22):
                    t = datetime(day.year, day.month, day.day, h, 0, tzinfo=IST)
                    bpm = int(rng.gauss({"Chinni": 88, "Ammamma": 76}.get(m["name"], 72), 6))
                    records.append(HealthRecordIn(id=f"seed-{mid}-{day}-hr{h}", type="heart_rate", start=t, end=t, value=bpm, unit="bpm"))
            upsert_health(conn, uid, SyncIn(member_id=mid, source="seed", records=records))
    print(f"Seeded {len(FAMILY)} members x {days} days for {DEMO_EMAIL}")


if __name__ == "__main__":
    seed()

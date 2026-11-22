"""Deterministic nutrition maths. No AI here.

Sources for the constants:
- BMR: Mifflin-St Jeor (1990): 10*kg + 6.25*cm - 5*age + 5 (men) or - 161 (women).
- Activity multipliers: the standard 1.2 / 1.375 / 1.55 / 1.725 set used with Mifflin-St Jeor.
- Protein: 0.83 g per kg body weight per day, ICMR-NIN Nutrient Requirements for Indians (2020), adults.
- Calorie floors: 1,200 kcal (women) and 1,500 kcal (men), the commonly used minimums below which
  diets need medical supervision; the target never goes below these or below BMR.
- Household measures: 1 cup = 240 g and 1 glass = 200 ml (INDB Units.xlsx); 1 tbsp = 15 ml and
  1 tsp = 5 ml (standard measures; liquids taken as 1 g/ml).
"""

from __future__ import annotations

from datetime import date

ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
GOAL_DELTA = {"maintain": 0, "lose": -500, "gain": 300}  # kcal/day; "lose" ~0.5 kg/week, a common gentle rate
PROTEIN_G_PER_KG = 0.83
FLOOR = {"female": 1200, "male": 1500}
MEASURE_G = {"g": 1, "gm": 1, "gram": 1, "grams": 1, "kg": 1000, "ml": 1, "l": 1000, "litre": 1000,
             "cup": 240, "cups": 240, "glass": 200, "glasses": 200,
             "tbsp": 15, "tablespoon": 15, "tablespoons": 15, "tsp": 5, "teaspoon": 5, "teaspoons": 5}
WEIGHT_UNITS = {"g", "gm", "gram", "grams", "kg", "ml", "l", "litre"}
KEYS = ("kcal", "protein", "carbs", "fat", "fibre")


def grams_for(food: dict, quantity: float, unit: str | None) -> float:
    """Convert '2 idli', '1 cup rice', '150 g' into grams for this food."""
    u = (unit or "").strip().lower()
    if u in WEIGHT_UNITS:
        return round(quantity * MEASURE_G[u], 1)
    food_unit = food["unit"].lower()
    if u in MEASURE_G and u != food_unit:  # cup, glass, tbsp, tsp are fixed measures, even for a "tall glass" dish
        return round(quantity * MEASURE_G[u], 1)
    # The food's own serving unit ("idli", "bowl") or a generic word means one INDB/USDA serving.
    if u in ("", "piece", "pieces", "serving", "servings", "portion", "nos", "no", "number") or u == food_unit or u in food_unit.split():
        return round(quantity * food["unit_g"], 1)
    return round(quantity * food["unit_g"], 1)  # plate, bowl, katori, slice...: one serving of this dish


def nutrients(per100: dict, grams: float) -> dict:
    return {k: round(per100[k] * grams / 100, 1) for k in KEYS}


def add(items: list[dict]) -> dict:
    return {k: round(sum(i[k] for i in items), 1) for k in KEYS}


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def bmr(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def targets(member: dict, on: date) -> dict:
    """Daily targets with safety rules applied in code.

    Children (<18) get no calorie or protein target: Mifflin-St Jeor is an adult equation and
    growing children should not be put on a deficit. Pregnancy keeps maintenance (no deficit).
    """
    notes: list[str] = []
    dob, w, h, sex = member.get("dob"), member.get("weight_kg"), member.get("height_cm"), member.get("sex")
    if not (dob and w and h and sex in FLOOR):
        return {"kcal": None, "protein_g": None, "bmr": None, "mode": "incomplete", "notes": ["profile_incomplete"]}
    dob = date.fromisoformat(dob) if isinstance(dob, str) else dob
    age = age_on(dob, on)
    if age < 18:
        return {"kcal": None, "protein_g": None, "bmr": None, "mode": "child", "notes": ["child_caution"]}
    b = bmr(sex, w, h, age)
    maintenance = b * ACTIVITY.get(member.get("activity") or "sedentary", 1.2)
    goal = member.get("goal") or "maintain"
    mode = "adult"
    if member.get("pregnant"):
        goal, mode = "maintain", "pregnancy"
        notes.append("pregnancy_caution")
    kcal = maintenance + GOAL_DELTA.get(goal, 0)
    floor = max(FLOOR[sex], b)
    if kcal < floor:
        kcal = floor
        notes.append("floor_applied")
    if age >= 65:
        notes.append("older_adult")
    return {"kcal": round(kcal), "protein_g": round(PROTEIN_G_PER_KG * w), "bmr": round(b),
            "maintenance": round(maintenance), "floor": round(floor), "mode": mode, "goal": goal, "notes": notes}

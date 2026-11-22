from datetime import date

import pytest

from healthbuddy import foods, nutrition

TODAY = date(2026, 11, 21)


def adult(**kw):
    return {"sex": "male", "dob": "1996-11-21", "height_cm": 175, "weight_kg": 70, "activity": "sedentary", "goal": "maintain", **kw}


def test_mifflin_st_jeor_matches_hand_calculation():
    # 10*70 + 6.25*175 - 5*30 + 5 = 1648.75 ; women use -161 instead of +5
    assert nutrition.bmr("male", 70, 175, 30) == pytest.approx(1648.75)
    assert nutrition.bmr("female", 60, 160, 40) == pytest.approx(10 * 60 + 6.25 * 160 - 5 * 40 - 161)


def test_age_counts_birthday_correctly():
    assert nutrition.age_on(date(2000, 11, 22), TODAY) == 25
    assert nutrition.age_on(date(2000, 11, 21), TODAY) == 26


def test_maintenance_target_and_protein():
    t = nutrition.targets(adult(activity="moderate"), TODAY)
    assert t["kcal"] == round(1648.75 * 1.55)
    assert t["protein_g"] == round(0.83 * 70)
    assert t["mode"] == "adult"


def test_weight_loss_never_goes_below_safe_floor():
    # Small sedentary woman: maintenance ~1,170, minus 500 would be ~670 kcal.
    t = nutrition.targets({"sex": "female", "dob": "1990-01-01", "height_cm": 150, "weight_kg": 45, "goal": "lose"}, TODAY)
    assert t["kcal"] >= 1200
    assert t["kcal"] >= t["bmr"]
    assert "floor_applied" in t["notes"]


def test_children_get_no_calorie_target():
    t = nutrition.targets(adult(dob="2015-06-15", goal="lose"), TODAY)
    assert t["kcal"] is None and t["mode"] == "child"


def test_pregnancy_forces_maintenance():
    m = {"sex": "female", "dob": "1994-02-01", "height_cm": 160, "weight_kg": 60, "goal": "lose", "pregnant": True}
    t = nutrition.targets(m, TODAY)
    assert t["mode"] == "pregnancy" and t["goal"] == "maintain"
    assert t["kcal"] == t["maintenance"]


def test_incomplete_profile_has_no_target():
    assert nutrition.targets({"sex": "female"}, TODAY)["mode"] == "incomplete"


def test_grams_for_units():
    idli = foods.get("idli")
    assert nutrition.grams_for(idli, 2, "") == round(2 * idli["unit_g"], 1)
    assert nutrition.grams_for(idli, 2, "idli") == round(2 * idli["unit_g"], 1)
    assert nutrition.grams_for(idli, 150, "g") == 150
    milk = foods.get("milk")
    assert nutrition.grams_for(milk, 1, "glass") == 200  # INDB Units: 1 glass = 200 ml
    assert nutrition.grams_for(foods.get("buttermilk"), 1, "glass") == 200  # not INDB's 423 g "tall glass"
    assert nutrition.grams_for(foods.get("rice"), 1, "cup") == 240


def test_nutrients_scale_linearly_and_add():
    per100 = {"kcal": 200, "protein": 10, "carbs": 30, "fat": 5, "fibre": 2}
    n = nutrition.nutrients(per100, 50)
    assert n == {"kcal": 100, "protein": 5, "carbs": 15, "fat": 2.5, "fibre": 1}
    assert nutrition.add([n, n])["kcal"] == 200

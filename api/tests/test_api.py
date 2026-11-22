from datetime import date

from conftest import signup

TODAY = date.today().isoformat()


def self_id(client):
    return client.get("/members").json()[0]["id"]


# ---------- auth ----------

def test_signup_requires_consent(client):
    r = client.post("/auth/signup", json={"email": "a@example.com", "password": "longenough1", "name": "A", "consent": False})
    assert r.status_code == 422


def test_session_cookie_is_http_only_and_password_is_hashed(client):
    r = signup(client)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    from healthbuddy import db
    with db.connect() as conn:
        h = conn.execute("SELECT pw_hash FROM users").fetchone()[0]
    assert h.startswith("$argon2") and "correct-horse-1" not in h


def test_login_logout_and_wrong_password(client):
    signup(client)
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/login", json={"email": "asha@example.com", "password": "nope-nope"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ASHA@example.com", "password": "correct-horse-1"}).status_code == 200
    assert client.get("/auth/me").json()["email"] == "asha@example.com"


def test_login_is_throttled_after_repeated_failures(client):
    signup(client)
    client.post("/auth/logout")
    for _ in range(5):
        client.post("/auth/login", json={"email": "asha@example.com", "password": "wrong-pass"})
    assert client.post("/auth/login", json={"email": "asha@example.com", "password": "correct-horse-1"}).status_code == 429


def test_duplicate_email_rejected(client):
    signup(client)
    assert client.post("/auth/signup", json={"email": "asha@example.com", "password": "longenough1", "name": "B", "consent": True}).status_code == 409


def test_bearer_token_for_android_companion(client):
    signup(client)
    client.post("/auth/logout")
    token = client.post("/auth/token", json={"email": "asha@example.com", "password": "correct-horse-1"}).json()["token"]
    client.cookies.clear()
    assert client.get("/members", headers={"Authorization": f"Bearer {token}"}).status_code == 200


# ---------- family ----------

def test_child_needs_parental_consent_and_gets_no_target(client):
    signup(client)
    child = {"name": "Chinni", "relation": "child", "sex": "female", "dob": "2016-01-01", "height_cm": 125, "weight_kg": 24}
    assert client.post("/members", json=child).status_code == 422
    r = client.post("/members", json={**child, "parental_consent": True, "goal": "lose"})
    assert r.status_code == 201
    m = r.json()
    assert m["is_minor"] and m["goal"] == "maintain" and m["targets"]["kcal"] is None


def test_users_cannot_see_each_others_members(client):
    signup(client)
    mine = client.post("/members", json={"name": "Ravi", "relation": "spouse"}).json()["id"]
    client.post("/auth/logout")
    signup(client, email="other@example.com")
    assert client.get(f"/members/{mine}/day").status_code == 404
    assert client.delete(f"/members/{mine}").status_code == 404
    assert client.post("/sync/health-connect", json={"member_id": mine, "records": []}).status_code == 404


def test_cannot_delete_own_profile(client):
    signup(client)
    assert client.delete(f"/members/{self_id(client)}").status_code == 422


# ---------- meals ----------

def test_meal_nutrients_are_recomputed_server_side(client):
    signup(client)
    mid = self_id(client)
    body = {"member_id": mid, "eaten_on": TODAY, "slot": "breakfast", "source": "search",
            "items": [{"food_id": "idli", "quantity": 2, "unit": ""}, {"food_id": "sambar", "quantity": 1, "unit": "", "grams": 100}]}
    assert client.post("/meals", json=body).status_code == 201
    from healthbuddy import foods, nutrition
    idli, sambar = foods.get("idli"), foods.get("sambar")
    expected = nutrition.nutrients(idli["per100"], round(2 * idli["unit_g"], 1))["kcal"] + nutrition.nutrients(sambar["per100"], 100)["kcal"]
    day = client.get(f"/members/{mid}/day").json()
    assert abs(day["totals"]["kcal"] - expected) < 0.2
    assert len(day["meals"]) == 1


def test_meal_rejects_unknown_food_and_bad_item(client):
    signup(client)
    mid = self_id(client)
    base = {"member_id": mid, "eaten_on": TODAY, "slot": "lunch", "source": "search"}
    assert client.post("/meals", json={**base, "items": [{"food_id": "nope", "quantity": 1}]}).status_code == 422
    assert client.post("/meals", json={**base, "items": [{"quantity": 1}]}).status_code == 422
    assert client.post("/meals", json={**base, "items": [{"food_id": "idli", "quantity": 1, "grams": 99999}]}).status_code == 422


def test_parse_text_endpoint_needs_login_and_uses_rules_without_ai(client):
    assert client.post("/meals/parse-text", json={"text": "2 idli"}).status_code == 401
    signup(client)
    out = client.post("/meals/parse-text", json={"text": "2 idli, sambar"}).json()
    assert out["engine"] == "rules" and [i["food"]["id"] for i in out["items"]] == ["idli", "sambar"]


# ---------- Health Connect sync ----------

def rec(rid, value, type_="steps", unit="count"):
    return {"id": rid, "type": type_, "start": f"{TODAY}T06:00:00+05:30", "end": f"{TODAY}T22:00:00+05:30", "value": value, "unit": unit}


def test_sync_is_idempotent_by_record_id(client):
    signup(client)
    mid = self_id(client)
    body = {"member_id": mid, "records": [rec("hc-1", 4000), rec("hc-2", 1500), rec("hc-s", 420, "sleep", "min")]}
    assert client.post("/sync/health-connect", json=body).json() == {"inserted": 3, "updated": 0, "unchanged": 0}
    assert client.post("/sync/health-connect", json=body).json() == {"inserted": 0, "updated": 0, "unchanged": 3}
    body["records"][0]["value"] = 4200  # Health Connect revised the record
    assert client.post("/sync/health-connect", json=body).json() == {"inserted": 0, "updated": 1, "unchanged": 2}
    health = client.get(f"/members/{mid}/day").json()["health"]
    assert health["steps"] == 5700 and health["sleep_min"] == 420 and health["sample"] is False


def test_sync_validates_units_and_timezones(client):
    signup(client)
    mid = self_id(client)
    assert client.post("/sync/health-connect", json={"member_id": mid, "records": [rec("x", 10, "steps", "kcal")]}).status_code == 422
    naive = rec("y", 10)
    naive["start"] = f"{TODAY}T06:00:00"
    assert client.post("/sync/health-connect", json={"member_id": mid, "records": [naive]}).status_code == 422


def test_sync_requires_auth(client):
    assert client.post("/sync/health-connect", json={"member_id": 1, "records": []}).status_code == 401


# ---------- privacy ----------

def test_export_and_delete_account(client):
    signup(client)
    mid = self_id(client)
    client.post("/sync/health-connect", json={"member_id": mid, "records": [rec("hc-1", 4000)]})
    data = client.get("/me/export").json()
    assert data["account"]["email"] == "asha@example.com"
    assert len(data["health_records"]) == 1 and "pw_hash" not in str(data)
    assert client.request("DELETE", "/me", json={"password": "wrong"}).status_code == 401
    assert client.request("DELETE", "/me", json={"password": "correct-horse-1"}).status_code == 200
    from healthbuddy import db
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM health_records").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0


def test_coach_without_ai_uses_rule_templates_and_child_caution(client):
    signup(client)
    child = client.post("/members", json={"name": "Chinni", "relation": "child", "sex": "female", "dob": "2016-01-01",
                                          "height_cm": 125, "weight_kg": 24, "parental_consent": True}).json()
    out = client.get(f"/members/{child['id']}/coach").json()
    assert out["engine"] == "rules" and "child" in out["cautions"] and out["suggestions"]


# ---------- coach: audit fixes ----------

def _adult(client):
    mid = self_id(client)
    client.put(f"/members/{mid}", json={"name": "Asha", "relation": "self", "sex": "female", "dob": "1990-01-01",
                                        "height_cm": 160, "weight_kg": 60})
    return mid


def _log(client, mid, day, slot, food="idli", qty=1):
    r = client.post("/meals", json={"member_id": mid, "eaten_on": day.isoformat(), "slot": slot, "source": "search",
                                    "items": [{"food_id": food, "quantity": qty}]})
    assert r.status_code == 201


def test_breakfast_only_days_do_not_trigger_eating_too_little(client):
    from datetime import timedelta
    signup(client)
    mid = _adult(client)
    for d in range(1, 5):
        _log(client, mid, date.today() - timedelta(days=d), "breakfast")
    out = client.get(f"/members/{mid}/coach").json()
    assert out["stats"]["days_logged"] == 0
    assert "below_floor" not in out["flags"] and "see_doctor" not in out["cautions"]


def test_week_leaves_out_today(client):
    signup(client)
    mid = _adult(client)
    for slot in ("breakfast", "lunch", "dinner"):
        _log(client, mid, date.today(), slot)
    out = client.get(f"/members/{mid}/coach").json()
    assert out["stats"]["days_logged"] == 0 and out["stats"]["to"] < date.today().isoformat()


def test_cached_ai_advice_is_dropped_when_numbers_change(client, monkeypatch):
    from datetime import timedelta

    from healthbuddy import coach, gemini
    calls = []

    def fake_generate(contents, schema):
        calls.append(1)
        return coach.CoachOut(suggestions=[coach.Suggestion(title="Add dal", body="A katori of dal with lunch.")]), "fake"

    monkeypatch.setattr(gemini, "generate", fake_generate)
    signup(client)
    mid = _adult(client)
    for d in range(1, 4):
        for slot in ("breakfast", "lunch", "dinner"):
            _log(client, mid, date.today() - timedelta(days=d), slot)
    assert client.get(f"/members/{mid}/coach").json()["engine"] == "gemini"
    client.get(f"/members/{mid}/coach")
    assert len(calls) == 1  # second view served from cache
    _log(client, mid, date.today() - timedelta(days=1), "snack", "banana")
    client.get(f"/members/{mid}/coach")
    assert len(calls) == 2  # new meal changed the stats, so the cache was not reused


def test_rotating_ips_still_hit_the_per_email_cap():
    from healthbuddy import auth
    auth._failures.clear()
    for i in range(19):
        auth.record_failure("asha@example.com", f"198.51.100.{i}")
    assert not auth.throttled("asha@example.com", "203.0.113.99")  # each IP below 5, email below 20
    auth.record_failure("asha@example.com", "198.51.100.200")
    assert auth.throttled("asha@example.com", "203.0.113.99")  # 20 failures across IPs blocks new IPs too
    auth._failures.clear()

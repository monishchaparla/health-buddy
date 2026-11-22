"""HTTP API. Run: uvicorn healthbuddy.api:app --reload --port 8000"""

from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field, model_validator

from healthbuddy import auth, coach, db, foods, gemini, nutrition, off, parse
from healthbuddy.auth import current_user
from healthbuddy.db import get_conn


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    yield


app = FastAPI(title="Health Buddy", lifespan=lifespan)

Lang = Literal["en", "te"]
Relation = Literal["self", "spouse", "child", "parent", "grandparent", "sibling", "other"]
HEALTH_UNITS = {"steps": "count", "sleep": "min", "active_kcal": "kcal", "heart_rate": "bpm"}


# ---------- models ----------

class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=60)
    lang: Lang = "en"
    consent: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    relation: Relation = "other"
    sex: Literal["male", "female"] | None = None
    dob: date | None = None
    height_cm: float | None = Field(default=None, ge=40, le=250)
    weight_kg: float | None = Field(default=None, ge=2, le=300)
    activity: Literal["sedentary", "light", "moderate", "active"] = "sedentary"
    goal: Literal["maintain", "lose", "gain"] = "maintain"
    pregnant: bool = False
    parental_consent: bool = False

    @model_validator(mode="after")
    def check(self):
        if self.dob and self.dob > date.today():
            raise ValueError("Date of birth can't be in the future.")
        if self.pregnant and self.sex == "male":
            raise ValueError("Pregnancy can only be set for a female member.")
        return self


class LangIn(BaseModel):
    lang: Lang


class ParseTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class MealItemIn(BaseModel):
    food_id: str | None = Field(default=None, max_length=40)
    barcode: str | None = Field(default=None, max_length=14)
    quantity: float = Field(gt=0, le=50)
    unit: str = Field(default="", max_length=20)
    grams: float | None = Field(default=None, gt=0, le=3000)

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.food_id) == bool(self.barcode):
            raise ValueError("Give either food_id or barcode.")
        return self


class MealIn(BaseModel):
    member_id: int
    eaten_on: date
    slot: Literal["breakfast", "lunch", "snack", "dinner"]
    source: Literal["text", "photo", "barcode", "search"]
    raw_text: str | None = Field(default=None, max_length=500)
    items: list[MealItemIn] = Field(min_length=1, max_length=20)


class HealthRecordIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    type: Literal["steps", "sleep", "active_kcal", "heart_rate"]
    start: datetime
    end: datetime
    value: float = Field(ge=0, le=200_000)
    unit: str

    @model_validator(mode="after")
    def check(self):
        if self.unit != HEALTH_UNITS[self.type]:
            raise ValueError(f"{self.type} must use unit {HEALTH_UNITS[self.type]}")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("timestamps need a UTC offset")
        if self.end < self.start:
            raise ValueError("end is before start")
        return self


class SyncIn(BaseModel):
    member_id: int
    source: str = Field(default="health_connect", max_length=40)
    records: list[HealthRecordIn] = Field(max_length=1000)


class DeleteMeIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


# ---------- helpers ----------

def member_row(conn: sqlite3.Connection, user: sqlite3.Row, member_id: int) -> dict:
    row = conn.execute("SELECT * FROM members WHERE id = ? AND user_id = ?", (member_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(404, "No such family member.")
    return dict(row)


def member_out(m: dict, on: date) -> dict:
    out = {k: m[k] for k in ("id", "name", "relation", "is_self", "sex", "dob", "height_cm", "weight_kg",
                             "activity", "goal", "pregnant")}
    out["is_self"], out["pregnant"] = bool(m["is_self"]), bool(m["pregnant"])
    out["is_minor"] = bool(m["dob"]) and nutrition.age_on(date.fromisoformat(m["dob"]), on) < 18
    out["targets"] = nutrition.targets(m, on)
    return out


def user_out(u: sqlite3.Row) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u["name"], "lang": u["lang"]}


def day_totals(conn: sqlite3.Connection, member_id: int, on: str) -> dict:
    r = conn.execute(
        """SELECT COALESCE(SUM(kcal),0) kcal, COALESCE(SUM(protein),0) protein, COALESCE(SUM(carbs),0) carbs,
                  COALESCE(SUM(fat),0) fat, COALESCE(SUM(fibre),0) fibre
           FROM meals m JOIN meal_items i ON i.meal_id = m.id WHERE m.member_id = ? AND m.eaten_on = ?""",
        (member_id, on)).fetchone()
    return {k: round(r[k], 1) for k in nutrition.KEYS}


def day_health(conn: sqlite3.Connection, member_id: int, on: str) -> dict:
    rows = conn.execute(
        """SELECT type, SUM(value) total, AVG(value) avg, MIN(value) lo, MAX(value) hi, MAX(source = 'seed') sample
           FROM health_records WHERE member_id = ?
             AND substr(CASE WHEN type = 'sleep' THEN end_time ELSE start_time END, 1, 10) = ?
           GROUP BY type""", (member_id, on)).fetchall()
    h = {r["type"]: r for r in rows}
    return {
        "steps": round(h["steps"]["total"]) if "steps" in h else None,
        "sleep_min": round(h["sleep"]["total"]) if "sleep" in h else None,
        "active_kcal": round(h["active_kcal"]["total"]) if "active_kcal" in h else None,
        "heart_rate": {"avg": round(h["heart_rate"]["avg"]), "min": round(h["heart_rate"]["lo"]),
                       "max": round(h["heart_rate"]["hi"])} if "heart_rate" in h else None,
        "sample": any(r["sample"] for r in rows),
    }


def food_for(conn: sqlite3.Connection, item: MealItemIn) -> dict:
    if item.barcode:
        if not off.valid(item.barcode):
            raise HTTPException(422, "Barcode must be 8 to 14 digits.")
        try:
            return off.lookup(conn, item.barcode)
        except off.NotFound as exc:
            raise HTTPException(404, str(exc)) from exc
    f = foods.get(item.food_id)
    if f is None:
        raise HTTPException(422, f"Unknown food {item.food_id}.")
    return f


# ---------- auth ----------

@app.get("/health")
def health():
    return {"ok": True, "ai": gemini.enabled()}


@app.post("/auth/signup", status_code=201)
def signup(body: SignupIn, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
    if not body.consent:
        raise HTTPException(422, "Agree to the health data notice to create an account.")
    email = body.email.lower()
    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("INSERT INTO users (email, pw_hash, name, lang, consent_at) VALUES (?, ?, ?, ?, ?)",
                       (email, auth.hash_password(body.password), body.name.strip(), body.lang, now))
    conn.execute("INSERT INTO members (user_id, name, relation, is_self) VALUES (?, ?, 'self', 1)",
                 (cur.lastrowid, body.name.strip()))
    auth.set_cookie(response, auth.create_session(conn, cur.lastrowid))
    return user_out(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


def _check_login(conn: sqlite3.Connection, body: LoginIn, request: Request) -> sqlite3.Row:
    email = body.email.lower()
    key = f"{email}|{request.client.host if request.client else '-'}"
    if auth.throttled(key):
        raise HTTPException(429, "Too many failed attempts. Wait 15 minutes and try again.")
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not auth.verify_password(user["pw_hash"] if user else None, body.password):
        auth.record_failure(key)
        raise HTTPException(401, "Email or password is wrong.")
    auth.clear_failures(key)
    return user


@app.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
    user = _check_login(conn, body, request)
    auth.set_cookie(response, auth.create_session(conn, user["id"]))
    return user_out(user)


@app.post("/auth/token")
def app_token(body: LoginIn, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    """Bearer token for the Android companion, which can't share the browser's cookie."""
    user = _check_login(conn, body, request)
    return {"token": auth.create_session(conn, user["id"], kind="app"), "user": user_out(user)}


@app.post("/auth/logout")
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
    auth.end_session(conn, auth.token_from(request))
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.get("/auth/me")
def me(user=Depends(current_user)):
    return user_out(user)


@app.put("/auth/lang")
def set_lang(body: LangIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    conn.execute("UPDATE users SET lang = ? WHERE id = ?", (body.lang, user["id"]))
    return {"lang": body.lang}


# ---------- family ----------

@app.get("/members")
def list_members(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute("SELECT * FROM members WHERE user_id = ? ORDER BY is_self DESC, id", (user["id"],)).fetchall()
    return [member_out(dict(r), date.today()) for r in rows]


def _member_values(body: MemberIn, existing: dict | None) -> dict:
    minor = body.dob is not None and nutrition.age_on(body.dob, date.today()) < 18
    consent_at = existing.get("parental_consent_at") if existing else None
    if minor:
        if not body.parental_consent and not consent_at:
            raise HTTPException(422, "Confirm you are this child's parent or guardian and consent to storing their data.")
        consent_at = consent_at or datetime.now(timezone.utc).isoformat()
    if minor and body.pregnant:
        raise HTTPException(422, "Pregnancy can't be set on a child's profile.")
    return {"name": body.name.strip(), "relation": body.relation, "sex": body.sex,
            "dob": body.dob.isoformat() if body.dob else None, "height_cm": body.height_cm, "weight_kg": body.weight_kg,
            "activity": body.activity, "goal": "maintain" if minor else body.goal, "pregnant": int(body.pregnant),
            "parental_consent_at": consent_at}


@app.post("/members", status_code=201)
def add_member(body: MemberIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    if body.relation == "self":
        raise HTTPException(422, "Your own profile already exists. Edit it instead.")
    if conn.execute("SELECT COUNT(*) FROM members WHERE user_id = ?", (user["id"],)).fetchone()[0] >= 12:
        raise HTTPException(422, "A family can have up to 12 members.")
    v = _member_values(body, None)
    cur = conn.execute(f"INSERT INTO members (user_id, {', '.join(v)}) VALUES (?, {', '.join('?' * len(v))})",
                       (user["id"], *v.values()))
    return member_out(member_row(conn, user, cur.lastrowid), date.today())


@app.put("/members/{member_id}")
def update_member(member_id: int, body: MemberIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    existing = member_row(conn, user, member_id)
    v = _member_values(body, existing)
    if existing["is_self"]:
        v["relation"] = "self"
    elif body.relation == "self":
        raise HTTPException(422, "Only your own profile can be 'self'.")
    conn.execute(f"UPDATE members SET {', '.join(f'{k} = ?' for k in v)} WHERE id = ?", (*v.values(), member_id))
    return member_out(member_row(conn, user, member_id), date.today())


@app.delete("/members/{member_id}")
def delete_member(member_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    m = member_row(conn, user, member_id)
    if m["is_self"]:
        raise HTTPException(422, "You can't remove your own profile. Delete your account instead.")
    conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    return {"ok": True}


# ---------- food and meal logging ----------

@app.get("/foods/search")
def search_foods(q: str = "", user=Depends(current_user)):
    return [parse.summary(f) for f in foods.search(q[:60], limit=20)]


@app.get("/foods/barcode/{code}")
def barcode(code: str, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    if not off.valid(code):
        raise HTTPException(422, "Barcode must be 8 to 14 digits.")
    try:
        return off.lookup(conn, code)
    except off.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Couldn't reach Open Food Facts. Check the connection or search for the food instead.") from exc


@app.post("/meals/parse-text")
def parse_text(body: ParseTextIn, user=Depends(current_user)):
    return parse.parse_text(body.text)


@app.post("/meals/parse-photo")
async def parse_photo(photo: UploadFile = File(...), user=Depends(current_user)):
    if photo.content_type not in ("image/jpeg", "image/png", "image/webp", "image/heic"):
        raise HTTPException(415, "Use a JPEG, PNG, WebP or HEIC photo.")
    data = await photo.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Photo is larger than 8 MB.")
    try:
        items, model = parse.parse_photo_ai(data, photo.content_type)
    except gemini.RateLimited as exc:
        raise HTTPException(503, "Photo reading is busy right now. Try again in a minute, or type the meal.") from exc
    except gemini.AIUnavailable as exc:
        raise HTTPException(503, "Photo reading isn't available. Type the meal or search for it instead.") from exc
    return {"engine": "gemini", "model": model, "items": items}


@app.post("/meals", status_code=201)
def save_meal(body: MealIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    member_row(conn, user, body.member_id)
    rows = []
    for it in body.items:  # nutrients are recomputed here from the database; client numbers are never trusted
        f = food_for(conn, it)
        grams = it.grams or nutrition.grams_for(f, it.quantity, it.unit)
        rows.append((f, it, grams, nutrition.nutrients(f["per100"], grams)))
    cur = conn.execute("INSERT INTO meals (member_id, eaten_on, slot, source, raw_text) VALUES (?, ?, ?, ?, ?)",
                       (body.member_id, body.eaten_on.isoformat(), body.slot, body.source, body.raw_text))
    for f, it, grams, n in rows:
        conn.execute(
            """INSERT INTO meal_items (meal_id, food_id, name, quantity, unit, grams, kcal, protein, carbs, fat, fibre,
                                       source, approx_of, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cur.lastrowid, f["id"], f["name"], it.quantity, it.unit or f["unit"], grams, *(n[k] for k in nutrition.KEYS),
             f["source"], f.get("approx_of"), f.get("note")))
    return {"id": cur.lastrowid, "totals": nutrition.add([r[3] for r in rows])}


@app.delete("/meals/{meal_id}")
def delete_meal(meal_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    row = conn.execute("SELECT m.id FROM meals m JOIN members b ON b.id = m.member_id WHERE m.id = ? AND b.user_id = ?",
                       (meal_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(404, "No such meal.")
    conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    return {"ok": True}


# ---------- dashboard ----------

@app.get("/members/{member_id}/day")
def member_day(member_id: int, on: date | None = None, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    on = on or date.today()
    m = member_row(conn, user, member_id)
    meals = []
    for meal in conn.execute("SELECT * FROM meals WHERE member_id = ? AND eaten_on = ? ORDER BY id", (member_id, on.isoformat())):
        items = [dict(i) for i in conn.execute("SELECT * FROM meal_items WHERE meal_id = ? ORDER BY id", (meal["id"],))]
        meals.append({"id": meal["id"], "slot": meal["slot"], "source": meal["source"], "raw_text": meal["raw_text"],
                      "items": items, "totals": nutrition.add(items)})
    return {"date": on.isoformat(), "member": member_out(m, on), "totals": day_totals(conn, member_id, on.isoformat()),
            "meals": meals, "health": day_health(conn, member_id, on.isoformat())}


@app.get("/family/overview")
def family_overview(on: date | None = None, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    on = on or date.today()
    out = []
    for r in conn.execute("SELECT * FROM members WHERE user_id = ? ORDER BY is_self DESC, id", (user["id"],)):
        m = dict(r)
        out.append({"member": member_out(m, on), "totals": day_totals(conn, m["id"], on.isoformat()),
                    "health": day_health(conn, m["id"], on.isoformat())})
    return {"date": on.isoformat(), "members": out}


@app.get("/members/{member_id}/coach")
def member_coach(member_id: int, on: date | None = None, refresh: bool = False, user=Depends(current_user),
                 conn: sqlite3.Connection = Depends(get_conn)):
    return coach.coach(conn, member_row(conn, user, member_id), on or date.today(), user["lang"], refresh)


# ---------- Health Connect sync (Android companion) ----------

def upsert_health(conn: sqlite3.Connection, user_id: int, body: SyncIn) -> dict:
    inserted = updated = unchanged = 0
    for r in body.records:
        row = (r.type, r.start.isoformat(), r.end.isoformat(), r.value, r.unit)
        old = conn.execute("SELECT member_id, type, start_time, end_time, value, unit FROM health_records WHERE user_id = ? AND record_id = ?",
                           (user_id, r.id)).fetchone()
        if old is None:
            conn.execute("""INSERT INTO health_records (user_id, member_id, record_id, type, start_time, end_time, value, unit, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (user_id, body.member_id, r.id, *row, body.source))
            inserted += 1
        elif tuple(old) == (body.member_id, *row):
            unchanged += 1
        else:
            conn.execute("""UPDATE health_records SET member_id = ?, type = ?, start_time = ?, end_time = ?, value = ?, unit = ?,
                            source = ?, updated_at = datetime('now') WHERE user_id = ? AND record_id = ?""",
                         (body.member_id, *row, body.source, user_id, r.id))
            updated += 1
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged}


@app.post("/sync/health-connect")
def sync_health(body: SyncIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    member_row(conn, user, body.member_id)
    return upsert_health(conn, user["id"], body)


# ---------- privacy (DPDP Act 2023) ----------

@app.get("/me/export")
def export(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    uid = user["id"]
    rows = lambda sql: [dict(r) for r in conn.execute(sql, (uid,))]  # noqa: E731
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {k: user[k] for k in ("email", "name", "lang", "consent_at", "created_at")},
        "members": rows("SELECT * FROM members WHERE user_id = ?"),
        "meals": rows("SELECT m.* FROM meals m JOIN members b ON b.id = m.member_id WHERE b.user_id = ?"),
        "meal_items": rows("""SELECT i.* FROM meal_items i JOIN meals m ON m.id = i.meal_id
                              JOIN members b ON b.id = m.member_id WHERE b.user_id = ?"""),
        "health_records": rows("SELECT * FROM health_records WHERE user_id = ?"),
    }
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="health-buddy-export.json"'})


@app.delete("/me")
def delete_me(body: DeleteMeIn, response: Response, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    if not auth.verify_password(user["pw_hash"], body.password):
        raise HTTPException(401, "Password is wrong. Your account was not deleted.")
    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))  # cascades to sessions, members, meals, health records
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}

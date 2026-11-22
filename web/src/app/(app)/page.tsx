"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, localDate, type Health, type Member, type Nutrients } from "@/lib/api";
import { fmt, useI18n, type MsgKey } from "@/lib/i18n";
import { MemberPicker, useApp } from "@/components/shell";
import { Caution, ThaliRing, useErrorText } from "@/components/ui";

type MealItem = { id: number; name: string; quantity: number; unit: string; grams: number; kcal: number; approx_of: string | null; note: string | null };
type Day = {
  date: string;
  member: Member;
  totals: Nutrients;
  meals: { id: number; slot: string; source: string; items: MealItem[]; totals: Nutrients }[];
  health: Health;
};
type Coach = {
  stats: { days_logged: number; from: string; to: string };
  cautions: string[];
  engine: "gemini" | "rules";
  notice: string | null;
  suggestions: { title: string; body: string }[];
};

const shift = (d: string, days: number) => {
  const x = new Date(`${d}T12:00:00`);
  x.setDate(x.getDate() + days);
  return localDate(x);
};

export default function TodayPage() {
  const { t } = useI18n();
  const { memberId, members } = useApp();
  const errorText = useErrorText();
  const [date, setDate] = useState(localDate());
  const [day, setDay] = useState<Day | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!memberId) return;
    try {
      setDay(await api<Day>(`/members/${memberId}/day?on=${date}`));
      setError("");
    } catch (e) {
      setError(errorText(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memberId, date]);

  useEffect(() => {
    load();
  }, [load]);

  const member = members.find((m) => m.id === memberId);
  const isToday = date === localDate();

  async function removeMeal(id: number, slot: string) {
    if (!confirm(t("meals.removeConfirm", { slot: t(`slot.${slot}` as MsgKey) }))) return;
    try {
      await api(`/meals/${id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="sr-only">{t("today.title")}</h1>
      <MemberPicker label={t("today.pick")} />

      <div className="flex items-center justify-between">
        <button type="button" className="grid h-11 w-11 place-items-center rounded-full hover:bg-surface" aria-label={t("today.prev")}
          onClick={() => setDate(shift(date, -1))}>
          <Chevron dir="left" />
        </button>
        <label className="flex flex-col items-center">
          <span className="sr-only">{t("today.date")}</span>
          <input type="date" value={date} max={localDate()} onChange={(e) => e.target.value && setDate(e.target.value)}
            className="rounded-[10px] bg-transparent px-2 py-1 text-center text-[17px] font-medium" />
        </label>
        <button type="button" className="grid h-11 w-11 place-items-center rounded-full hover:bg-surface disabled:opacity-30"
          aria-label={t("today.next")} disabled={isToday} onClick={() => setDate(shift(date, 1))}>
          <Chevron dir="right" />
        </button>
      </div>

      {error && <p role="alert" className="panel p-4 text-kokum">{error}</p>}
      {day && member && <DayView day={day} onRemove={removeMeal} />}
      {member && <CoachPanel memberId={member.id} name={member.name} />}
    </div>
  );
}

function DayView({ day, onRemove }: { day: Day; onRemove: (id: number, slot: string) => void }) {
  const { t } = useI18n();
  const target = day.member.targets;
  const kcal = day.totals.kcal;
  const diff = target.kcal ? Math.round(target.kcal - kcal) : null;

  return (
    <>
      <section aria-label={t("today.title")} className="panel flex flex-col items-center gap-4 px-4 pb-5 pt-6">
        <ThaliRing eaten={kcal} target={target.kcal} />
        {diff !== null ? (
          <p className={`text-[15px] font-medium ${diff < 0 ? "text-kokum" : "text-ink-2"}`}>
            {diff < 0 ? t("today.over", { n: fmt(-diff) }) : t("today.left", { n: fmt(diff) })}
          </p>
        ) : (
          <p className="text-[15px] text-ink-2">{t("today.noTarget")}</p>
        )}
        <ul className="grid w-full grid-cols-4 gap-2">
          <Katori label={t("macro.protein")} grams={day.totals.protein} target={target.protein_g} color="var(--protein)" />
          <Katori label={t("macro.carbs")} grams={day.totals.carbs} color="var(--carbs)" />
          <Katori label={t("macro.fat")} grams={day.totals.fat} color="var(--fat)" />
          <Katori label={t("macro.fibre")} grams={day.totals.fibre} color="var(--dusk)" />
        </ul>
      </section>

      {target.mode === "child" && <Caution>{t("caution.child")}</Caution>}
      {target.mode === "pregnancy" && <Caution>{t("caution.pregnancy")}</Caution>}
      {target.mode === "incomplete" && <Caution>{t("target.profile_incomplete")}</Caution>}
      {target.notes.includes("floor_applied") && target.floor && (
        <p className="text-[13px] text-ink-2">{t("target.floor_applied", { n: fmt(target.floor) })}</p>
      )}

      <HealthStrip health={day.health} />

      <section aria-labelledby="meals-h" className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <h2 id="meals-h" className="text-[20px] font-semibold">{t("meals.title")}</h2>
          <Link href="/log" className="text-[15px] font-medium text-indigo underline-offset-2 hover:underline">{t("meals.logFirst")}</Link>
        </div>
        {day.meals.length === 0 ? (
          <p className="panel p-4 text-ink-2">{t("meals.empty", { name: day.member.name })}</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {day.meals.map((m) => (
              <li key={m.id} className="panel p-4">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-medium">{t(`slot.${m.slot}` as MsgKey)}</h3>
                  <div className="flex items-center gap-1">
                    <span className="num text-[15px] text-ink-2">{t("common.kcal", { n: fmt(m.totals.kcal) })}</span>
                    <button type="button" aria-label={t("meals.remove")} onClick={() => onRemove(m.id, m.slot)}
                      className="grid h-11 w-11 place-items-center rounded-full text-ink-2 hover:bg-canvas">
                      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <path d="M5 7h14M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
                      </svg>
                    </button>
                  </div>
                </div>
                <ul className="mt-1 divide-y divide-rule">
                  {m.items.map((i) => (
                    <li key={i.id} className="flex justify-between gap-3 py-2 text-[15px]">
                      <span>
                        {i.name}
                        <span className="text-ink-2"> · {fmt(i.quantity, 1)} {i.unit} ({fmt(i.grams)} g)</span>
                        {i.approx_of && <span className="block text-[13px] text-ink-2">{t("log.approx", { name: i.approx_of })}</span>}
                        {i.note === "fried" && <span className="block text-[13px] text-ink-2">{t("log.fried")}</span>}
                      </span>
                      <span className="num shrink-0 text-ink-2">{fmt(i.kcal)}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

function Katori({ label, grams, target, color }: { label: string; grams: number; target?: number | null; color: string }) {
  const { t } = useI18n();
  const size = 56, r = 24, c = 2 * Math.PI * r;
  const share = target ? Math.min(grams / target, 1) : 0;
  return (
    <li className="flex flex-col items-center gap-1 text-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={28} cy={28} r={r} fill="var(--canvas)" stroke="var(--rule)" strokeWidth={4} />
        <circle cx={28} cy={28} r={r} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={target ? c * (1 - share) : 0} transform="rotate(-90 28 28)" opacity={target ? 1 : 0.85} />
        <text x="50%" y="56%" textAnchor="middle" fill="var(--ink)" fontSize="15" fontWeight="600" className="num">{Math.round(grams)}</text>
      </svg>
      <span className="text-[13px] font-medium leading-tight">{label}</span>
      <span className="text-[13px] leading-tight text-ink-2">{target ? t("macro.ofTarget", { n: target }) : t("macro.grams")}</span>
    </li>
  );
}

function HealthStrip({ health }: { health: Health }) {
  const { t } = useI18n();
  const none = health.steps === null && health.sleep_min === null && health.heart_rate === null;
  return (
    <section aria-labelledby="health-h" className="panel p-4">
      <h2 id="health-h" className="text-[15px] font-medium text-ink-2">{t("health.title")}</h2>
      {none ? (
        <p className="mt-1 text-[15px] text-ink-2">{t("health.none")}</p>
      ) : (
        <dl className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label={t("health.steps")} value={health.steps !== null ? fmt(health.steps) : "–"} />
          <Stat label={t("health.sleep")} value={health.sleep_min !== null
            ? t("health.sleepValue", { h: Math.floor(health.sleep_min / 60), m: health.sleep_min % 60 }) : "–"} />
          <Stat label={t("health.active")} value={health.active_kcal !== null ? t("common.kcal", { n: fmt(health.active_kcal) }) : "–"} />
          <Stat label={t("health.hr")} value={health.heart_rate ? t("health.hrValue", { n: health.heart_rate.avg }) : "–"} />
        </dl>
      )}
      {health.sample && <p className="mt-3 text-[13px] text-ink-2">{t("health.sample")}</p>}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[13px] text-ink-2">{label}</dt>
      <dd className="num text-[17px] font-semibold">{value}</dd>
    </div>
  );
}

function CoachPanel({ memberId, name }: { memberId: number; name: string }) {
  const { t, lang } = useI18n();
  const errorText = useErrorText();
  const [coach, setCoach] = useState<Coach | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (refresh = false) => {
    setBusy(true);
    try {
      setCoach(await api<Coach>(`/members/${memberId}/coach?on=${localDate()}${refresh ? "&refresh=true" : ""}`));
      setError("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memberId, lang]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section aria-labelledby="coach-h" aria-busy={busy} className="flex flex-col gap-3">
      <h2 id="coach-h" className="text-[20px] font-semibold">{t("coach.title")}</h2>
      {error && <p role="alert" className="text-kokum">{error}</p>}
      {!coach && busy && <p className="panel p-4 text-ink-2">{t("coach.loading")}</p>}
      {coach && (
        <>
          {coach.cautions.map((c) => <Caution key={c}>{t(`caution.${c}` as MsgKey)}</Caution>)}
          <ul className="flex flex-col gap-3">
            {coach.suggestions.map((s, i) => (
              <li key={i} className="panel p-4">
                <h3 className="font-medium">{s.title}</h3>
                <p className="mt-1 text-[15px] text-ink-2">{s.body}</p>
              </li>
            ))}
          </ul>
          <p className="text-[13px] text-ink-2">
            {t("coach.basedOn", { days: coach.stats.days_logged, from: coach.stats.from, to: coach.stats.to })}{" "}
            {coach.engine === "gemini" ? t("coach.byAi", { name }) : coach.notice === "ai_rate_limited" ? t("coach.aiBusy") : t("coach.byRules")}
          </p>
          <button type="button" className="btn btn-secondary self-start" disabled={busy} onClick={() => load(true)}>
            {busy ? t("coach.loading") : t("coach.refresh")}
          </button>
        </>
      )}
    </section>
  );
}

function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d={dir === "left" ? "m15 6-6 6 6 6" : "m9 6 6 6-6 6"} />
    </svg>
  );
}

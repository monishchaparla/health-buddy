"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, localDate, type Health, type Member, type Nutrients } from "@/lib/api";
import { fmt, useI18n, type MsgKey } from "@/lib/i18n";
import { useApp } from "@/components/shell";
import { ErrorText, Field, ThaliRing, useErrorText } from "@/components/ui";

type Overview = { date: string; members: { member: Member; totals: Nutrients; health: Health }[] };

const RELATIONS = ["spouse", "child", "parent", "grandparent", "sibling", "other"] as const;
const ACTIVITY = ["sedentary", "light", "moderate", "active"] as const;
const GOALS = ["maintain", "lose", "gain"] as const;

const isMinor = (dob: string) => {
  if (!dob) return false;
  const d = new Date(`${dob}T00:00:00`), now = new Date();
  const age = now.getFullYear() - d.getFullYear() - (now < new Date(now.getFullYear(), d.getMonth(), d.getDate()) ? 1 : 0);
  return age < 18;
};

export default function FamilyPage() {
  const { t } = useI18n();
  const router = useRouter();
  const { setMemberId, reloadMembers } = useApp();
  const errorText = useErrorText();
  const [data, setData] = useState<Overview | null>(null);
  const [editing, setEditing] = useState<Member | "new" | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api<Overview>(`/family/overview?on=${localDate()}`));
    } catch (e) {
      setError(errorText(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const done = async () => {
    setEditing(null);
    await Promise.all([load(), reloadMembers()]);
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-[26px] font-semibold">{t("family.title")}</h1>
        {editing === null && <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>{t("family.add")}</button>}
      </div>
      <ErrorText>{error}</ErrorText>

      {editing !== null ? (
        <MemberForm member={editing === "new" ? null : editing} onDone={done} onCancel={() => setEditing(null)} />
      ) : (
        <section aria-labelledby="overview-h" className="flex flex-col gap-3">
          <h2 id="overview-h" className="text-[15px] font-medium text-ink-2">{t("family.overview")}</h2>
          <ul className="flex flex-col gap-3">
            {data?.members.map(({ member: m, totals, health }) => (
              <li key={m.id} className="panel flex items-center gap-4 p-4">
                <button type="button" className="shrink-0 rounded-full" aria-label={`${m.name}: ${t("nav.today")}`}
                  onClick={() => { setMemberId(m.id); router.push("/"); }}>
                  <ThaliRing eaten={totals.kcal} target={m.targets.kcal} size={56} />
                </button>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">
                    {m.name}{" "}
                    <span className="text-[13px] font-normal text-ink-2">
                      {m.is_self ? t("family.you") : t(`relation.${m.relation}` as MsgKey)}
                    </span>
                  </p>
                  <p className="num text-[15px] text-ink-2">
                    {m.targets.kcal ? `${fmt(totals.kcal)} / ${t("common.kcal", { n: fmt(m.targets.kcal) })}` : t("common.kcal", { n: fmt(totals.kcal) })}
                    {health.steps !== null && ` · ${fmt(health.steps)} ${t("health.steps").toLowerCase()}`}
                  </p>
                  {health.sample && <p className="text-[13px] text-ink-2">{t("family.sampleBadge")}</p>}
                </div>
                <button type="button" className="btn btn-secondary min-h-11 shrink-0 px-3" onClick={() => setEditing(m)}>{t("common.edit")}</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function MemberForm({ member, onDone, onCancel }: { member: Member | null; onDone: () => void; onCancel: () => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const [dob, setDob] = useState(member?.dob ?? "");
  const [sex, setSex] = useState(member?.sex ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const minor = isMinor(dob);
  const isSelf = member?.is_self ?? false;

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const num = (k: string) => (f.get(k) ? Number(f.get(k)) : null);
    const body = {
      name: f.get("name"), relation: isSelf ? "self" : f.get("relation"), sex: sex || null, dob: dob || null,
      height_cm: num("height_cm"), weight_kg: num("weight_kg"), activity: f.get("activity"),
      goal: minor ? "maintain" : f.get("goal"), pregnant: f.get("pregnant") === "on", parental_consent: f.get("consent") === "on",
    };
    setBusy(true);
    setError("");
    try {
      await api(member ? `/members/${member.id}` : "/members", { method: member ? "PUT" : "POST", json: body });
      onDone();
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  async function remove() {
    if (!member || !confirm(t("family.removeConfirm", { name: member.name }))) return;
    try {
      await api(`/members/${member.id}`, { method: "DELETE" });
      onDone();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form onSubmit={submit} className="panel flex flex-col gap-4 p-5">
      <h2 className="text-[20px] font-semibold">{member ? t("family.editTitle", { name: member.name }) : t("family.addTitle")}</h2>
      <Field id="m-name" label={t("field.name")}>
        <input id="m-name" name="name" required maxLength={60} defaultValue={member?.name} className="field" />
      </Field>
      {!isSelf && (
        <Field id="m-rel" label={t("field.relation")}>
          <select id="m-rel" name="relation" defaultValue={member?.relation ?? "spouse"} className="field">
            {RELATIONS.map((r) => <option key={r} value={r}>{t(`relation.${r}` as MsgKey)}</option>)}
          </select>
        </Field>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field id="m-sex" label={t("field.sex")}>
          <select id="m-sex" value={sex} onChange={(e) => setSex(e.target.value)} className="field">
            <option value="">{t("field.notSet")}</option>
            <option value="female">{t("sex.female")}</option>
            <option value="male">{t("sex.male")}</option>
          </select>
        </Field>
        <Field id="m-dob" label={t("field.dob")}>
          <input id="m-dob" type="date" max={localDate()} value={dob} onChange={(e) => setDob(e.target.value)} className="field" />
        </Field>
        <Field id="m-h" label={t("field.height")}>
          <input id="m-h" name="height_cm" type="number" inputMode="decimal" min={40} max={250} step="0.1" defaultValue={member?.height_cm ?? ""} className="field num" />
        </Field>
        <Field id="m-w" label={t("field.weight")}>
          <input id="m-w" name="weight_kg" type="number" inputMode="decimal" min={2} max={300} step="0.1" defaultValue={member?.weight_kg ?? ""} className="field num" />
        </Field>
      </div>
      <Field id="m-act" label={t("field.activity")}>
        <select id="m-act" name="activity" defaultValue={member?.activity ?? "sedentary"} className="field">
          {ACTIVITY.map((a) => <option key={a} value={a}>{t(`activity.${a}` as MsgKey)}</option>)}
        </select>
      </Field>
      {minor ? (
        <p className="text-[15px] text-ink-2">{t("goal.childNote")}</p>
      ) : (
        <Field id="m-goal" label={t("field.goal")}>
          <select id="m-goal" name="goal" defaultValue={member?.goal ?? "maintain"} className="field">
            {GOALS.map((g) => <option key={g} value={g}>{t(`goal.${g}` as MsgKey)}</option>)}
          </select>
        </Field>
      )}
      {sex === "female" && !minor && (
        <label className="flex items-center gap-3 text-[15px]">
          <input type="checkbox" name="pregnant" defaultChecked={member?.pregnant} className="h-5 w-5 accent-[var(--indigo)]" />
          {t("field.pregnant")}
        </label>
      )}
      {minor && !member?.is_minor && (
        <label className="flex items-start gap-3 rounded-[12px] bg-canvas p-3 text-[15px]">
          <input type="checkbox" name="consent" required className="mt-1 h-5 w-5 shrink-0 accent-[var(--indigo)]" />
          <span>{t("field.parentalConsent")}</span>
        </label>
      )}
      <ErrorText>{error}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={busy}>{t("common.save")}</button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>{t("common.cancel")}</button>
        {member && !isSelf && <button type="button" className="btn btn-danger ml-auto" onClick={remove}>{t("common.remove")}</button>}
      </div>
    </form>
  );
}

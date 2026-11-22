"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { readPref, useI18n, writePref, type MsgKey } from "@/lib/i18n";

/** Turn an API error into a sentence for the user. Server messages are English-only; the network case is translated. */
export function useErrorText() {
  const { t } = useI18n();
  return (e: unknown) => {
    if (e instanceof ApiError) return e.status === 0 ? t("error.network") : e.message || t("error.generic");
    return t("error.generic");
  };
}

export function Caution({ children }: { children: React.ReactNode }) {
  return (
    <div role="note" className="flex gap-3 rounded-[16px] bg-turmeric-wash p-4 text-[15px] text-turmeric-ink">
      <svg aria-hidden="true" viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5M12 8h.01" strokeLinecap="round" />
      </svg>
      <p>{children}</p>
    </div>
  );
}

export function ErrorText({ children }: { children?: React.ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="text-[15px] text-kokum">
      {children}
    </p>
  );
}

export function Field({ label, hint, children, id }: { label: string; hint?: string; children: React.ReactNode; id: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[15px] font-medium">
        {label}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="text-[13px] text-ink-2">
          {hint}
        </p>
      )}
    </div>
  );
}

/** The day's calorie ring: turmeric fill on a steel track. With no target it shows intake only. */
export function ThaliRing({ eaten, target, size = 200 }: { eaten: number; target: number | null; size?: number }) {
  const { t } = useI18n();
  const stroke = size >= 120 ? 14 : 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const share = target ? Math.min(eaten / target, 1) : 0;
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(share));
    return () => cancelAnimationFrame(id);
  }, [share]);
  const big = size >= 120;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={target ? `${Math.round(eaten)} ${t("today.of", { n: target })}` : `${Math.round(eaten)} ${t("today.eaten")}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="var(--surface)" stroke="var(--rule)" strokeWidth={stroke} />
      {target ? (
        <circle className="ring-fill" cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--turmeric)" strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - shown)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      ) : null}
      {big ? (
        <>
          <text x="50%" y="47%" textAnchor="middle" fill="var(--ink)" fontSize="40" fontWeight="600" className="num">
            {Math.round(eaten).toLocaleString("en-IN")}
          </text>
          <text x="50%" y="62%" textAnchor="middle" fill="var(--ink-2)" fontSize="14">
            {target ? t("today.of", { n: target.toLocaleString("en-IN") }) : t("today.eaten")}
          </text>
        </>
      ) : null}
    </svg>
  );
}

export function Segmented<V extends string>({ value, options, onChange, label }: {
  value: V; options: { value: V; label: string }[]; onChange: (v: V) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid gap-1 rounded-[12px] border border-rule bg-surface p-1"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={`min-h-10 rounded-[9px] px-2 text-[15px] font-medium ${value === o.value ? "bg-indigo-wash text-indigo" : "text-ink-2"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

type Theme = "system" | "light" | "dark";
export function applyTheme(theme: Theme) {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  writePref("hb_theme", theme);
}
export function currentTheme(): Theme {
  const v = readPref("hb_theme");
  return v === "light" || v === "dark" ? v : "system";
}
function isDark() {
  const v = document.documentElement.dataset.theme;
  return v ? v === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeToggle() {
  const { t } = useI18n();
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(isDark()), []);
  const next = dark ? "light" : "dark";
  return (
    <button type="button" className="grid h-11 w-11 place-items-center rounded-full text-ink-2 hover:bg-surface"
      aria-label={t("theme.toggle", { mode: t(`theme.${next}` as MsgKey) })}
      onClick={() => { applyTheme(next); setDark(!dark); }}>
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        {dark ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>
          : <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />}
      </svg>
    </button>
  );
}

export function LangToggle() {
  const { t, lang, setLang } = useI18n();
  return (
    <button type="button" lang={lang === "en" ? "te" : "en"} aria-label={t("lang.switchLabel")} onClick={() => setLang(lang === "en" ? "te" : "en")}
      className="h-11 rounded-full px-3 text-[15px] font-medium text-indigo hover:bg-surface">
      {t("lang.switch")}
    </button>
  );
}

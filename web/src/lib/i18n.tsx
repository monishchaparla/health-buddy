"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import en from "@/messages/en.json";
import te from "@/messages/te.json";

export type Lang = "en" | "te";
export type MsgKey = keyof typeof en;
const MESSAGES: Record<Lang, Record<string, string>> = { en, te };

type T = (k: MsgKey, vars?: Record<string, string | number>) => string;
const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: T }>({ lang: "en", setLang: () => {}, t: (k) => k });

export function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writePref(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {}
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    const saved = readPref("hb_lang");
    if (saved === "en" || saved === "te") setLangState(saved);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = MESSAGES[lang]["app.name"];
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    writePref("hb_lang", l);
  }, []);

  const t = useCallback<T>(
    (k, vars) => {
      let s = MESSAGES[lang][k] ?? en[k] ?? k;
      if (vars) for (const [name, v] of Object.entries(vars)) s = s.replaceAll(`{${name}}`, String(v));
      return s;
    },
    [lang],
  );

  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);

export function fmt(n: number, digits = 0) {
  return n.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

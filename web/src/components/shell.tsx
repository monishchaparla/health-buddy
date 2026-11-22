"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiError, type Member } from "@/lib/api";
import { readPref, useI18n, writePref, type MsgKey } from "@/lib/i18n";
import { LangToggle, ThemeToggle } from "./ui";

type User = { id: number; email: string; name: string; lang: "en" | "te" };
type AppCtx = {
  user: User;
  members: Member[];
  memberId: number;
  setMemberId: (id: number) => void;
  reloadMembers: () => Promise<void>;
};
const Ctx = createContext<AppCtx | null>(null);
export const useApp = () => useContext(Ctx)!;

const NAV: { href: string; key: MsgKey; icon: string }[] = [
  { href: "/", key: "nav.today", icon: "M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1Z" },
  { href: "/log", key: "nav.log", icon: "M12 5v14M5 12h14" },
  { href: "/family", key: "nav.family", icon: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3 20a6 6 0 0 1 12 0M17 11a2.5 2.5 0 1 0 0-5M21 20a5 5 0 0 0-4-4.9" },
  { href: "/settings", key: "nav.settings", icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, lang, setLang } = useI18n();
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberId, setMemberIdState] = useState(0);
  const [error, setError] = useState("");

  const reloadMembers = useCallback(async () => {
    const list = await api<Member[]>("/members");
    setMembers(list);
    setMemberIdState((cur) => {
      const saved = Number(readPref("hb_member"));
      const want = cur || saved;
      return list.some((m) => m.id === want) ? want : list[0]?.id ?? 0;
    });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const me = await api<User>("/auth/me");
        setUser(me);
        await reloadMembers();
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else setError(t("error.network"));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the server's language preference in sync so the coach writes in the language the user reads.
  useEffect(() => {
    if (user && user.lang !== lang) {
      api("/auth/lang", { method: "PUT", json: { lang } }).then(() => setUser({ ...user, lang })).catch(() => {});
    }
  }, [lang, user]);

  useEffect(() => {
    if (user && !readPref("hb_lang")) setLang(user.lang);
  }, [user, setLang]);

  useEffect(() => {
    document.title = t("app.name"); // route changes reset the title to the English metadata
  }, [path, t]);

  const setMemberId = (id: number) => {
    setMemberIdState(id);
    writePref("hb_member", String(id));
  };

  return (
    <div className="mx-auto flex min-h-dvh max-w-[640px] flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:rounded-[10px] focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="flex items-center justify-between px-4 pt-3">
        <Link href="/" className="text-[20px] font-semibold tracking-tight">{t("app.name")}</Link>
        <div className="flex items-center">
          <LangToggle />
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="flex-1 px-4 pb-28 pt-2">
        {error ? <p role="alert" className="panel p-4 text-kokum">{error}</p>
          : user ? <Ctx.Provider value={{ user, members, memberId, setMemberId, reloadMembers }}>{children}</Ctx.Provider>
          : <p className="p-4 text-ink-2" aria-live="polite">{t("common.loading")}</p>}
      </main>
      <nav aria-label={t("nav.main")} className="fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-surface/95 backdrop-blur pb-[env(safe-area-inset-bottom)]">
        <ul className="mx-auto grid max-w-[640px] grid-cols-4">
          {NAV.map((n) => {
            const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <li key={n.href}>
                <Link href={n.href} aria-current={active ? "page" : undefined}
                  className={`flex min-h-[60px] flex-col items-center justify-center gap-0.5 text-[13px] font-medium ${active ? "text-indigo" : "text-ink-2"}`}>
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d={n.icon} />
                  </svg>
                  {t(n.key)}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}

/** Member chips: one tap to switch whose day you're looking at or logging for. */
export function MemberPicker({ label }: { label: string }) {
  const { members, memberId, setMemberId } = useApp();
  return (
    <div role="radiogroup" aria-label={label} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
      {members.map((m) => (
        <button key={m.id} type="button" role="radio" aria-checked={m.id === memberId} onClick={() => setMemberId(m.id)}
          className={`flex min-h-11 shrink-0 items-center gap-2 rounded-full border pl-1.5 pr-4 text-[15px] font-medium ${
            m.id === memberId ? "border-indigo bg-indigo-wash text-indigo" : "border-rule bg-surface text-ink"}`}>
          <span aria-hidden="true" className="grid h-8 w-8 place-items-center rounded-full bg-canvas text-[14px] font-semibold text-ink">
            {m.name.slice(0, 1).toUpperCase()}
          </span>
          {m.name}
        </button>
      ))}
    </div>
  );
}

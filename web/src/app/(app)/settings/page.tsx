"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n, type Lang } from "@/lib/i18n";
import { useApp } from "@/components/shell";
import { applyTheme, currentTheme, ErrorText, Field, Segmented, useErrorText } from "@/components/ui";

export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { user } = useApp();
  const router = useRouter();
  const errorText = useErrorText();
  const [theme, setTheme] = useState<"system" | "light" | "dark">("system");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setTheme(currentTheme()), []);

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/login");
  }

  async function deleteAccount(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const password = new FormData(e.currentTarget).get("password");
    setBusy(true);
    setError("");
    try {
      await api("/me", { method: "DELETE", json: { password } });
      router.replace("/signup");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[26px] font-semibold">{t("settings.title")}</h1>

      <section className="panel flex flex-col gap-4 p-5">
        <div className="flex flex-col gap-2">
          <span className="text-[15px] font-medium">{t("settings.language")}</span>
          <Segmented<Lang> label={t("settings.language")} value={lang} onChange={setLang}
            options={[{ value: "en", label: "English" }, { value: "te", label: "తెలుగు" }]} />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-[15px] font-medium">{t("settings.theme")}</span>
          <Segmented label={t("settings.theme")} value={theme} onChange={(v) => { setTheme(v); applyTheme(v); }}
            options={[{ value: "system", label: t("settings.themeSystem") }, { value: "light", label: t("settings.themeLight") },
              { value: "dark", label: t("settings.themeDark") }]} />
        </div>
      </section>

      <section aria-labelledby="acct-h" className="panel flex flex-col gap-3 p-5">
        <h2 id="acct-h" className="text-[20px] font-semibold">{t("settings.account")}</h2>
        <p className="text-[15px] text-ink-2">{t("settings.signedInAs", { email: user.email })}</p>
        <button type="button" className="btn btn-secondary self-start" onClick={signOut}>{t("auth.signout")}</button>
      </section>

      <section aria-labelledby="data-h" className="panel flex flex-col gap-3 p-5">
        <h2 id="data-h" className="text-[20px] font-semibold">{t("settings.data")}</h2>
        <p className="text-[15px] text-ink-2">{t("settings.exportHint")}</p>
        <a href="/api/me/export" download className="btn btn-secondary self-start">{t("settings.export")}</a>
        <form onSubmit={deleteAccount} className="mt-3 flex flex-col gap-3 border-t border-rule pt-4">
          <h3 className="font-medium text-kokum">{t("settings.deleteTitle")}</h3>
          <p className="text-[15px] text-ink-2">{t("settings.deleteBody")}</p>
          <Field id="del-pw" label={t("settings.deletePassword")}>
            <input id="del-pw" name="password" type="password" autoComplete="current-password" required className="field" />
          </Field>
          <ErrorText>{error}</ErrorText>
          <button className="btn btn-danger self-start" disabled={busy}>{t("settings.deleteButton")}</button>
        </form>
      </section>

      <section aria-labelledby="about-h" className="flex flex-col gap-2">
        <h2 id="about-h" className="text-[15px] font-medium">{t("settings.about")}</h2>
        <p className="text-[15px] text-ink-2">{t("settings.aboutBody")}</p>
      </section>
    </div>
  );
}

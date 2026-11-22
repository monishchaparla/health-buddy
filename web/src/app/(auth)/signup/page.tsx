"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ErrorText, Field, useErrorText } from "@/components/ui";

export default function SignupPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const errorText = useErrorText();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (!f.get("consent")) {
      setError(t("auth.consentRequired"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/auth/signup", {
        method: "POST",
        json: { name: f.get("name"), email: f.get("email"), password: f.get("password"), lang, consent: true },
      });
      router.replace("/family");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[26px] font-semibold leading-tight">{t("auth.signupTitle")}</h1>
      <form onSubmit={submit} className="panel flex flex-col gap-4 p-5">
        <Field id="name" label={t("auth.name")}>
          <input id="name" name="name" autoComplete="name" required maxLength={60} className="field" />
        </Field>
        <Field id="email" label={t("auth.email")}>
          <input id="email" name="email" type="email" autoComplete="email" spellCheck={false} required className="field" />
        </Field>
        <Field id="password" label={t("auth.password")} hint={t("auth.passwordHint")}>
          <input id="password" name="password" type="password" autoComplete="new-password" required minLength={8}
            aria-describedby="password-hint" className="field" />
        </Field>
        <section aria-labelledby="consent-title" className="rounded-[12px] bg-canvas p-4">
          <h2 id="consent-title" className="font-medium">{t("auth.consentTitle")}</h2>
          <p className="mt-1 text-[15px] text-ink-2">{t("auth.consentBody")}</p>
          <label className="mt-3 flex items-start gap-3 text-[15px]">
            <input type="checkbox" name="consent" className="mt-1 h-5 w-5 shrink-0 accent-[var(--indigo)]" />
            <span>{t("auth.consentCheck")}</span>
          </label>
        </section>
        <ErrorText>{error}</ErrorText>
        <button className="btn btn-primary" disabled={busy}>{t("auth.signup")}</button>
      </form>
      <p className="text-center text-[15px] text-ink-2">
        {t("auth.haveAccount")}{" "}
        <Link href="/login" className="font-medium text-indigo underline underline-offset-2">{t("auth.signin")}</Link>
      </p>
    </div>
  );
}

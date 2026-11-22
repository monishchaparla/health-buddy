"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ErrorText, Field, useErrorText } from "@/components/ui";

export default function LoginPage() {
  const { t } = useI18n();
  const router = useRouter();
  const errorText = useErrorText();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", { method: "POST", json: { email: f.get("email"), password: f.get("password") } });
      router.replace("/");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-semibold leading-tight">{t("auth.signinTitle")}</h1>
        <p className="mt-1 text-ink-2">{t("app.tagline")}</p>
      </div>
      <form onSubmit={submit} className="panel flex flex-col gap-4 p-5">
        <Field id="email" label={t("auth.email")}>
          <input id="email" name="email" type="email" autoComplete="email" required className="field" />
        </Field>
        <Field id="password" label={t("auth.password")}>
          <input id="password" name="password" type="password" autoComplete="current-password" required className="field" />
        </Field>
        <ErrorText>{error}</ErrorText>
        <button className="btn btn-primary" disabled={busy}>{t("auth.signin")}</button>
      </form>
      <p className="text-center text-[15px] text-ink-2">
        {t("auth.noAccount")}{" "}
        <Link href="/signup" className="font-medium text-indigo underline underline-offset-2">{t("auth.signup")}</Link>
      </p>
    </div>
  );
}

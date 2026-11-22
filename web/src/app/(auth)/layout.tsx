"use client";

import { useI18n } from "@/lib/i18n";
import { LangToggle, ThemeToggle } from "@/components/ui";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="mx-auto flex min-h-dvh max-w-[440px] flex-col px-4">
      <header className="flex items-center justify-between pt-3">
        <span className="text-[20px] font-semibold tracking-tight">{t("app.name")}</span>
        <div className="flex items-center">
          <LangToggle />
          <ThemeToggle />
        </div>
      </header>
      <main className="flex flex-1 flex-col justify-center py-8">{children}</main>
    </div>
  );
}

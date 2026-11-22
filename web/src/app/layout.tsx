import type { Metadata, Viewport } from "next";
import { Anek_Telugu } from "next/font/google";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

const anek = Anek_Telugu({ variable: "--font-anek", subsets: ["latin", "telugu"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Health Buddy",
  description: "Meals, steps and sleep for the whole family, in English and Telugu.",
  applicationName: "Health Buddy",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#edf0f3" },
    { media: "(prefers-color-scheme: dark)", color: "#10141b" },
  ],
};

// Applies a saved light/dark choice before first paint so the page doesn't flash.
const themeScript = `try{var t=localStorage.getItem("hb_theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={anek.variable}>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, localDate, type Food, type ReviewItem } from "@/lib/api";
import { fmt, useI18n, type MsgKey } from "@/lib/i18n";
import { MemberPicker, useApp } from "@/components/shell";
import { ErrorText, Field, Segmented, useErrorText } from "@/components/ui";

type Method = "text" | "photo" | "barcode" | "search";
type Slot = "breakfast" | "lunch" | "snack" | "dinner";
type Entry = {
  key: number;
  food?: Food;
  input: string;
  quantity: number;
  unit: string;
  gramsPerUnit: number; // grams for quantity 1, so the stepper can rescale
  barcode?: string;
  confidence: number;
  candidates?: Food[];
};
type ParseOut = { engine: "gemini" | "rules"; items: ReviewItem[] };

let nextKey = 1;
const slotNow = (): Slot => {
  const h = new Date().getHours();
  return h < 11 ? "breakfast" : h < 16 ? "lunch" : h < 19 ? "snack" : "dinner";
};

function fromReview(i: ReviewItem): Entry {
  return {
    key: nextKey++, food: i.food, input: i.input, quantity: i.quantity, unit: i.unit || i.food?.unit || "",
    gramsPerUnit: i.grams && i.quantity ? i.grams / i.quantity : i.food?.unit_g ?? 0, confidence: i.confidence,
    candidates: i.matched ? undefined : i.candidates,
  };
}

function fromFood(food: Food, barcode?: string): Entry {
  return { key: nextKey++, food, input: food.name, quantity: 1, unit: food.unit, gramsPerUnit: food.unit_g, barcode, confidence: 1 };
}

export default function LogPage() {
  const { t } = useI18n();
  const { members, memberId } = useApp();
  const errorText = useErrorText();
  const [date, setDate] = useState(localDate());
  const [slot, setSlot] = useState<Slot>(slotNow());
  const [method, setMethod] = useState<Method>("text");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [engine, setEngine] = useState<"gemini" | "rules" | null>(null);
  const [rawText, setRawText] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);
  const member = members.find((m) => m.id === memberId);

  // Warn before leaving with reviewed items that were never saved.
  useEffect(() => {
    if (entries.length === 0) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [entries.length]);

  const add = (items: Entry[]) => {
    setEntries((cur) => [...cur, ...items]);
    setSaved("");
  };
  const update = (key: number, patch: Partial<Entry>) => setEntries((cur) => cur.map((e) => (e.key === key ? { ...e, ...patch } : e)));
  const drop = (key: number) => setEntries((cur) => cur.filter((e) => e.key !== key));

  const ready = entries.filter((e) => e.food);
  const total = ready.reduce((s, e) => s + (e.food!.per100.kcal * e.gramsPerUnit * e.quantity) / 100, 0);

  async function save() {
    if (!member || ready.length === 0) return;
    setBusy(true);
    setError("");
    try {
      await api("/meals", {
        method: "POST",
        json: {
          member_id: member.id, eaten_on: date, slot, source: method, raw_text: method === "text" ? rawText.slice(0, 500) : null,
          items: ready.map((e) => ({
            ...(e.barcode ? { barcode: e.barcode } : { food_id: e.food!.id }),
            quantity: e.quantity, unit: e.unit, grams: Math.round(e.gramsPerUnit * e.quantity * 10) / 10,
          })),
        },
      });
      setEntries([]);
      setEngine(null);
      setRawText("");
      setSaved(t("log.saved", { name: member.name }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-[26px] font-semibold">{t("log.title")}</h1>
      <MemberPicker label={t("log.for")} />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Segmented label={t("log.slot")} value={slot} onChange={setSlot}
            options={(["breakfast", "lunch", "snack", "dinner"] as Slot[]).map((s) => ({ value: s, label: t(`slot.${s}` as MsgKey) }))} />
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-[13px] text-ink-2">{t("log.date")}</span>
          <input type="date" className="field sm:w-[160px]" value={date} max={localDate()} onChange={(e) => e.target.value && setDate(e.target.value)} />
        </label>
      </div>

      <section aria-labelledby="method-h" className="flex flex-col gap-3">
        <h2 id="method-h" className="text-[15px] font-medium text-ink-2">{t("log.method")}</h2>
        <Segmented label={t("log.method")} value={method} onChange={(m) => { setMethod(m); setError(""); }}
          options={[{ value: "text", label: t("log.type") }, { value: "photo", label: t("log.photo") },
            { value: "barcode", label: t("log.barcode") }, { value: "search", label: t("log.search") }]} />
        <div className="panel p-4">
          {method === "text" && <TypeTab text={rawText} setText={setRawText} onItems={(o) => { setEngine(o.engine); add(o.items.map(fromReview)); }} />}
          {method === "photo" && <PhotoTab onItems={(o) => { setEngine(o.engine); add(o.items.map(fromReview)); }} />}
          {method === "barcode" && <BarcodeTab onFood={(f, code) => add([fromFood(f, code)])} />}
          {method === "search" && <SearchTab onFood={(f) => add([fromFood(f)])} />}
        </div>
      </section>

      <section aria-labelledby="review-h" className="flex flex-col gap-3">
        <h2 id="review-h" className="text-[20px] font-semibold">{t("log.review")}</h2>
        {engine && entries.length > 0 && <p className="text-[13px] text-ink-2">{engine === "gemini" ? t("log.byAi") : t("log.byRules")}</p>}
        {entries.length === 0 ? (
          <p className="panel p-4 text-ink-2">{t("log.reviewEmpty")}</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {entries.map((e) => <ReviewRow key={e.key} e={e} update={update} drop={drop} />)}
          </ul>
        )}
        {ready.length > 0 && (
          <div className="flex items-center justify-between gap-3 border-t border-rule pt-3">
            <p className="font-medium">{t("log.total")}: <span className="num">{t("common.kcal", { n: fmt(total) })}</span></p>
            <button type="button" className="btn btn-primary" onClick={save} disabled={busy}>{t("log.save")}</button>
          </div>
        )}
        <ErrorText>{error}</ErrorText>
        {saved && (
          <p role="status" className="panel p-4">
            {saved} <Link href="/" className="font-medium text-indigo underline underline-offset-2">{t("nav.today")}</Link>
          </p>
        )}
      </section>
    </div>
  );
}

function ReviewRow({ e, update, drop }: { e: Entry; update: (k: number, p: Partial<Entry>) => void; drop: (k: number) => void }) {
  const { t, lang } = useI18n();
  if (!e.food) {
    return (
      <li className="panel p-4">
        <p className="text-[15px]">{t("log.unmatched", { name: e.input })}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {(e.candidates ?? []).map((c) => (
            <button key={c.id} type="button" className="btn btn-secondary min-h-10 px-3"
              onClick={() => update(e.key, { food: c, candidates: undefined, unit: c.unit, gramsPerUnit: c.unit_g })}>
              {lang === "te" && c.name_te ? c.name_te : c.name}
            </button>
          ))}
          <button type="button" className="btn min-h-10 px-3 text-ink-2" onClick={() => drop(e.key)}>{t("log.skip")}</button>
        </div>
      </li>
    );
  }
  const f = e.food;
  const grams = e.gramsPerUnit * e.quantity;
  const name = lang === "te" && f.name_te ? f.name_te : f.name;
  return (
    <li className="panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">{name}</p>
          <p className="num text-[13px] text-ink-2">{t("log.perUnit", { unit: e.unit || f.unit, g: fmt(e.gramsPerUnit) })} · {f.source}</p>
        </div>
        <p className="num shrink-0 font-medium">{t("common.kcal", { n: fmt((f.per100.kcal * grams) / 100) })}</p>
      </div>
      {f.approx_of && <p className="mt-1 text-[13px] text-ink-2">{t("log.approx", { name: f.approx_of })}</p>}
      {f.note === "fried" && <p className="mt-1 text-[13px] text-ink-2">{t("log.fried")}</p>}
      {e.confidence < 0.5 && <p className="mt-1 text-[13px] text-kokum">{t("log.lowConfidence")}</p>}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2" role="group" aria-label={t("log.quantity")}>
          <button type="button" className="btn btn-secondary h-11 w-11 p-0" aria-label={t("log.decrease", { name: f.name })}
            onClick={() => update(e.key, { quantity: Math.max(0.5, e.quantity - 0.5) })}>−</button>
          <span className="num min-w-20 text-center" aria-live="polite">{fmt(e.quantity, 1)} <span className="text-[13px] text-ink-2">({fmt(grams)} g)</span></span>
          <button type="button" className="btn btn-secondary h-11 w-11 p-0" aria-label={t("log.increase", { name: f.name })}
            onClick={() => update(e.key, { quantity: Math.min(50, e.quantity + 0.5) })}>+</button>
        </div>
        <button type="button" className="btn min-h-11 px-3 text-ink-2" onClick={() => drop(e.key)}>{t("common.remove")}</button>
      </div>
    </li>
  );
}

function TypeTab({ text, setText, onItems }: { text: string; setText: (s: string) => void; onItems: (o: ParseOut) => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function read(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      onItems(await api<ParseOut>("/meals/parse-text", { method: "POST", json: { text: text.trim() } }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={read} className="flex flex-col gap-3">
      <Field id="meal-text" label={t("log.typeLabel")} hint={t("log.typeHint")}>
        <textarea id="meal-text" autoComplete="off" className="field" maxLength={500} value={text} onChange={(e) => setText(e.target.value)} aria-describedby="meal-text-hint" />
      </Field>
      <ErrorText>{error}</ErrorText>
      <button className="btn btn-secondary self-start" disabled={busy || !text.trim()}>{busy ? t("log.reading") : t("log.read")}</button>
    </form>
  );
}

function PhotoTab({ onItems }: { onItems: (o: ParseOut) => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  async function read() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("photo", file);
      onItems(await api<ParseOut>("/meals/parse-photo", { method: "POST", body }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-col gap-3">
      <Field id="meal-photo" label={t("log.photoLabel")} hint={t("log.photoHint")}>
        <input id="meal-photo" type="file" accept="image/jpeg,image/png,image/webp,image/heic" capture="environment" aria-describedby="meal-photo-hint"
          className="text-[15px] file:mr-3 file:min-h-11 file:rounded-[10px] file:border file:border-rule file:bg-surface file:px-4 file:font-medium file:text-ink"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            setFile(f);
            setPreview(f ? URL.createObjectURL(f) : "");
          }} />
      </Field>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {preview && <img src={preview} alt="" width={640} height={448} className="max-h-56 w-full rounded-[12px] object-cover" />}
      <ErrorText>{error}</ErrorText>
      <button type="button" className="btn btn-secondary self-start" disabled={!file || busy} onClick={read}>
        {busy ? t("log.reading") : t("log.photoRead")}
      </button>
    </div>
  );
}

type Detector = { detect: (src: CanvasImageSource) => Promise<{ rawValue: string }[]> };
declare global {
  interface Window { BarcodeDetector?: new (o: { formats: string[] }) => Detector }
}

function BarcodeTab({ onFood }: { onFood: (f: Food, code: string) => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const [code, setCode] = useState("");
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);

  const stop = () => {
    stream.current?.getTracks().forEach((tr) => tr.stop());
    stream.current = null;
    setScanning(false);
  };
  useEffect(() => stop, []);

  async function lookup(c: string) {
    if (!/^\d{8,14}$/.test(c)) return;
    setBusy(true);
    setError("");
    try {
      onFood(await api<Food>(`/foods/barcode/${c}`), c);
      setCode("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function scan() {
    if (!window.BarcodeDetector || !navigator.mediaDevices) {
      setError(t("log.noCamera"));
      return;
    }
    try {
      const detector = new window.BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      setScanning(true);
      setError("");
      requestAnimationFrame(async function tick() {
        const v = video.current;
        if (!stream.current) return;
        if (!v) return void setTimeout(() => requestAnimationFrame(tick), 100);
        if (!v.srcObject) {
          v.srcObject = stream.current;
          await v.play().catch(() => {});
        }
        const found = await detector.detect(v).catch(() => []);
        if (found[0]?.rawValue) {
          stop();
          setCode(found[0].rawValue);
          lookup(found[0].rawValue);
        } else setTimeout(() => requestAnimationFrame(tick), 250);
      });
    } catch {
      stop();
      setError(t("log.cameraError"));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); lookup(code); }}>
        <Field id="barcode" label={t("log.barcodeLabel")} hint={t("log.barcodeHint")}>
          <input id="barcode" inputMode="numeric" autoComplete="off" spellCheck={false} maxLength={14} className="field num" value={code}
            aria-describedby="barcode-hint" onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
        </Field>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-secondary" disabled={busy || !/^\d{8,14}$/.test(code)}>{t("log.lookup")}</button>
          <button type="button" className="btn btn-secondary" onClick={scanning ? stop : scan}>{scanning ? t("log.stopScan") : t("log.scan")}</button>
        </div>
      </form>
      {scanning && <video ref={video} muted playsInline className="max-h-64 w-full rounded-[12px] bg-ink object-cover" />}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

function SearchTab({ onFood }: { onFood: (f: Food) => void }) {
  const { t, lang } = useI18n();
  const errorText = useErrorText();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Food[] | null>(null);
  const [error, setError] = useState("");
  const [added, setAdded] = useState("");
  useEffect(() => {
    const id = setTimeout(async () => {
      try {
        setResults(await api<Food[]>(`/foods/search?q=${encodeURIComponent(q.trim())}`));
        setError("");
      } catch (e) {
        setError(errorText(e));
      }
    }, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);
  return (
    <div className="flex flex-col gap-3">
      <Field id="food-q" label={t("log.searchLabel")}>
        <input id="food-q" type="search" autoComplete="off" className="field" placeholder={t("log.searchHint")} value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <p role="status" className="sr-only">{added}</p>
      {results && results.length === 0 && <p className="text-[15px] text-ink-2">{t("log.noResults")}</p>}
      <ul className="max-h-80 divide-y divide-rule overflow-y-auto">
        {results?.map((f) => {
          const other = lang === "te" ? f.name : f.name_te;
          return (
            <li key={f.id} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <p className="truncate font-medium">{lang === "te" && f.name_te ? f.name_te : f.name}</p>
                <p className="num truncate text-[13px] text-ink-2">
                  {other ? `${other} · ` : ""}{t("log.perUnit", { unit: f.unit, g: fmt(f.unit_g) })} · {t("common.kcal", { n: fmt((f.per100.kcal * f.unit_g) / 100) })}
                </p>
              </div>
              <button type="button" className="btn btn-secondary min-h-10 shrink-0 px-3"
                onClick={() => { onFood(f); setAdded(t("log.added", { name: f.name })); }}>{t("log.add")}</button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

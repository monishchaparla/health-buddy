// Thin fetch wrapper for the FastAPI backend behind the /api rewrite.
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Detail = string | { msg: string }[] | undefined;

function message(detail: Detail, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) return detail.map((d) => d.msg.replace(/^Value error, /, "")).join(" ");
  return fallback;
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...rest,
      headers: json === undefined ? headers : { "content-type": "application/json", ...headers },
      body: json === undefined ? rest.body : JSON.stringify(json),
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "");
  }
  if (!res.ok) {
    let detail: Detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = undefined;
    }
    throw new ApiError(res.status, message(detail, ""));
  }
  return (await res.json()) as T;
}

export const localDate = (d = new Date()) => d.toLocaleDateString("en-CA"); // YYYY-MM-DD in the user's time zone

export type Nutrients = { kcal: number; protein: number; carbs: number; fat: number; fibre: number };
export type Targets = {
  kcal: number | null;
  protein_g: number | null;
  floor?: number;
  mode: "adult" | "child" | "pregnancy" | "incomplete";
  notes: string[];
};
export type Member = {
  id: number;
  name: string;
  relation: string;
  is_self: boolean;
  sex: "male" | "female" | null;
  dob: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  activity: string;
  goal: string;
  pregnant: boolean;
  is_minor: boolean;
  targets: Targets;
};
export type Health = {
  steps: number | null;
  sleep_min: number | null;
  active_kcal: number | null;
  heart_rate: { avg: number; min: number; max: number } | null;
  sample: boolean;
};
export type Food = {
  id: string;
  name: string;
  name_te: string;
  unit: string;
  unit_g: number;
  per100: Nutrients;
  source: string;
  approx_of: string | null;
  note: string | null;
};
export type ReviewItem = {
  input: string;
  matched: boolean;
  food?: Food;
  quantity: number;
  unit: string;
  grams?: number;
  confidence: number;
  nutrients?: Nutrients;
  candidates?: Food[];
};

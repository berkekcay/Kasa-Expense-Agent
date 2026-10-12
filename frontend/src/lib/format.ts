// Display helpers. Money comes from the API as decimal strings ("1234.50"); these only format
// it, they never do arithmetic on it. Dates come as ISO strings ("2026-10-12").

const moneyFormatters = new Map<string, Intl.NumberFormat>();

function moneyFormatter(currency: string): Intl.NumberFormat | null {
  const code = (currency || "TRY").toUpperCase();
  let f = moneyFormatters.get(code);
  if (!f) {
    try {
      f = new Intl.NumberFormat("tr-TR", { style: "currency", currency: code });
    } catch {
      return null; // not an ISO 4217 code
    }
    moneyFormatters.set(code, f);
  }
  return f;
}

/** "1234.5" + "TRY" -> "₺1.234,50". Decimal strings are formatted exactly (no float math). */
export function formatMoney(amount: string | null | undefined, currency: string): string {
  if (amount === null || amount === undefined || amount === "") return "";
  const f = moneyFormatter(currency);
  if (!f) return `${amount} ${currency}`;
  // Intl.NumberFormat accepts decimal strings and formats them without converting to a float.
  return f.format(amount as Intl.StringNumericLiteral);
}

const plainNumber = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 });

/** Chart axis and tooltip numbers (already floats, drawing only). */
export function formatNumber(value: number): string {
  return plainNumber.format(value);
}

const axisNumber = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
/** Axis ticks: whole numbers with Turkish grouping ("12.000"). */
export function formatAxis(value: number): string {
  return axisNumber.format(value);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function parseDay(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
}

/** "2026-10-12" -> "12 Oct 2026". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = parseDay(iso);
  return d ? `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` : iso;
}

/** "2026-10-01" or "2026-10" -> "Oct 2026". */
export function formatMonth(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = parseDay(iso.length === 7 ? `${iso}-01` : iso);
  return d ? `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` : iso;
}

/** Backend datetimes are UTC; naive ones get a Z. Shown in the viewer's time zone. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const withZone = /Z|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(withZone);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Local "today" as YYYY-MM-DD. Call only in the browser (event handlers, after hydration). */
export function todayIso(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "2026-10" -> "2026-10-01" (the API's month parameter); "" stays undefined. */
export function monthParam(month: string): string | undefined {
  return month ? `${month}-01` : undefined;
}

/**
 * Normalises what people type into an amount field to the API's "1234.56" form, or null.
 * Accepts "84,90", "84.90", "1.249,00" (Turkish grouping) and "1,249.00".
 * Pure string handling, no float conversion.
 */
export function normalizeAmount(input: string): string | null {
  const s = input.replace(/[\s₺]/g, "");
  if (!s) return null;
  let out: string;
  if (/^\d{1,3}(\.\d{3})+(,\d{1,2})?$/.test(s)) out = s.replace(/\./g, "").replace(",", ".");
  else if (/^\d{1,3}(,\d{3})+(\.\d{1,2})?$/.test(s)) out = s.replace(/,/g, "");
  else out = s.replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(out)) return null;
  if (/^0+(\.0+)?$/.test(out)) return null;
  return out;
}

/** "12.5" -> 1250 (integer minor units) for live form checks. Exact string math. */
export function toMinor(amount: string): number {
  const [whole, frac = ""] = amount.split(".");
  return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}

/** 1250 -> "12.50". Inverse of toMinor, for showing what is left in a live form check. */
export function fromMinor(minor: number): string {
  const sign = minor < 0 ? "-" : "";
  const abs = Math.abs(minor);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** "33.33" percent -> 3333 hundredths, or null when it is not a valid percent. */
export function percentToHundredths(input: string): number | null {
  const s = input.trim().replace(",", ".");
  if (!s) return 0;
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(s)) return null;
  const v = toMinor(s);
  return v > 10000 ? null : v;
}

export function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

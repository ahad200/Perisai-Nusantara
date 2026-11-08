// Format waktu: selalu sertakan zona (WIB/UTC), dan waktu relatif berdampingan
// dengan absolut (PRD Lampiran C.2).
const WIB = "Asia/Jakarta";

function fmt(dt: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("id-ID", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(dt);
}

export function formatWIB(iso: string | Date): string {
  const dt = typeof iso === "string" ? new Date(iso) : iso;
  return `${fmt(dt, WIB)} WIB`;
}

export function formatUTC(iso: string | Date): string {
  const dt = typeof iso === "string" ? new Date(iso) : iso;
  return `${fmt(dt, "UTC")} UTC`;
}

export function clockParts(now: Date = new Date()): { wib: string; utc: string } {
  const t = (tz: string) =>
    new Intl.DateTimeFormat("id-ID", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(now);
  return { wib: t(WIB), utc: t("UTC") };
}

export function relative(iso: string | Date, now: Date = new Date()): string {
  const dt = typeof iso === "string" ? new Date(iso) : iso;
  const diffMs = dt.getTime() - now.getTime();
  const abs = Math.abs(diffMs);
  const rtf = new Intl.RelativeTimeFormat("id", { numeric: "auto" });
  const min = 60_000;
  const hour = 60 * min;
  const day = 24 * hour;
  if (abs < min) return rtf.format(Math.round(diffMs / 1000), "second");
  if (abs < hour) return rtf.format(Math.round(diffMs / min), "minute");
  if (abs < day) return rtf.format(Math.round(diffMs / hour), "hour");
  return rtf.format(Math.round(diffMs / day), "day");
}

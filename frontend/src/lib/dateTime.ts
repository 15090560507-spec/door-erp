export function localDateYmd(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function localDateCompact(date = new Date()): string {
  return localDateYmd(date).replace(/-/g, "");
}

export function localDateDots(date = new Date()): string {
  return localDateYmd(date).replace(/-/g, ".");
}

export function normalizeDateYmd(value: string): string {
  return String(value || "").trim().replace(/[./]/g, "-").slice(0, 10);
}

export function isLocalToday(value: string, date = new Date()): boolean {
  return normalizeDateYmd(value) === localDateYmd(date);
}

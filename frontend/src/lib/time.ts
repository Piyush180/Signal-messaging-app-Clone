// One place for all time formatting. Because the backend now emits consistent
// ISO-8601 timestamps WITH a timezone, we never need the old "+Z" patch hack.

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatDayLabel(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (same(d, today)) return "Today";
  if (same(d, yesterday)) return "Yesterday";
  return d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

export function dayKey(iso: string): string {
  return new Date(iso).toDateString();
}

export function lastSeenText(iso: string | null): string {
  if (!iso) return "Offline";
  return `Last seen ${formatTime(iso)}`;
}

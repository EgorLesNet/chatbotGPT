export type ChatKind = "message" | "buy" | "problem";

export type ChatMessage = {
  id: number;
  user_id: number;
  author_name: string;
  avatar_path: string | null;
  body: string;
  kind: string;
  task_id: number | null;
  task_title: string | null;
  has_photo: boolean;
  sent_at: string;
};

export const KIND_LABEL: Record<string, string> = {
  buy: "🛒 Нужно купить",
  problem: "⚠️ Проблема",
};

export function formatTime(sentAt: string): string {
  const hasZone = /[zZ]$|[+-]\d\d:?\d\d$/.test(sentAt);
  const d = new Date(hasZone ? sentAt : `${sentAt}Z`);
  if (Number.isNaN(d.getTime())) return "";
  const time = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === new Date().toDateString()) return time;
  return `${d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}, ${time}`;
}

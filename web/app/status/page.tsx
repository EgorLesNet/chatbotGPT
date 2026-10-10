import { headers } from "next/headers";

export const dynamic = "force-dynamic";
export const metadata = { title: "Статус сервисов" };

type State = "operational" | "degraded" | "outage" | "unknown";
type Row = { name: string; note: string; state: State };

const LABEL: Record<State, string> = {
  operational: "Работает",
  degraded: "Есть перебои",
  outage: "Недоступен",
  unknown: "Нет данных",
};

function asState(value: unknown): State {
  return value === "operational" || value === "degraded" || value === "outage" ? value : "unknown";
}

async function reachable(url: string): Promise<State> {
  try {
    const res = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    return res.status < 500 ? "operational" : "outage";
  } catch {
    return "outage";
  }
}

async function botServices(origin: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${origin}/api/health`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (!res.ok) return null;
    const data = (await res.json()) as { services?: Record<string, unknown> };
    return data && typeof data.services === "object" && data.services ? data.services : null;
  } catch {
    return null;
  }
}

export default async function StatusPage() {
  const h = headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "";
  const proto = h.get("x-forwarded-proto") ?? "https";
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;

  const [bot, auth, data] = await Promise.all([
    host ? botServices(`${proto}://${host}`) : Promise.resolve(null),
    supabaseUrl ? reachable(`${supabaseUrl}/auth/v1/health`) : Promise.resolve<State>("unknown"),
    supabaseUrl ? reachable(`${supabaseUrl}/rest/v1/`) : Promise.resolve<State>("unknown"),
  ]);

  const botDown = bot === null;
  const rows: Row[] = [
    { name: "Веб-приложение", note: "Сайт и личный кабинет", state: "operational" },
    { name: "Telegram-бот", note: "Приём и обработка сообщений", state: botDown ? "unknown" : asState(bot?.telegram) },
    { name: "Сервер бота", note: "Обработка команд и задач", state: botDown ? "outage" : asState(bot?.api) },
    { name: "База данных", note: "Хранение объектов и задач", state: botDown ? "unknown" : asState(bot?.database) },
    { name: "Авторизация", note: "Вход и регистрация", state: auth },
    { name: "Хранилище данных сайта", note: "Доступ к объектам в приложении", state: data },
  ];

  const states = rows.map((r) => r.state);
  const overall: State = states.includes("outage")
    ? "outage"
    : states.includes("degraded") || states.includes("unknown")
      ? "degraded"
      : "operational";
  const headline =
    overall === "operational"
      ? "Все системы работают"
      : overall === "degraded"
        ? "Есть частичные перебои"
        : "Сбой в работе сервисов";

  const checkedAt = new Date().toLocaleString("ru-RU", {
    timeZone: "Europe/Moscow",
    day: "2-digit",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <main className="st">
      <style>{CSS}</style>
      <header className="st-head">
        <p className="st-eyebrow">ProrabTask</p>
        <h1>Статус сервисов</h1>
      </header>

      <section className={`st-banner st-${overall}`} aria-live="polite">
        <span className="st-dot" aria-hidden="true" />
        <div>
          <strong>{headline}</strong>
          <span>Проверено {checkedAt} (МСК)</span>
        </div>
      </section>

      <ul className="st-list">
        {rows.map((row) => (
          <li key={row.name} className="st-row">
            <div>
              <span className="st-name">{row.name}</span>
              <span className="st-note">{row.note}</span>
            </div>
            <span className={`st-pill st-${row.state}`}>
              <span className="st-dot" aria-hidden="true" />
              {LABEL[row.state]}
            </span>
          </li>
        ))}
      </ul>

      <footer className="st-foot">
        <p>Страница показывает только общее состояние сервисов. Данных пользователей и технических подробностей здесь нет.</p>
        <a href="/status" className="st-refresh">Обновить</a>
      </footer>
    </main>
  );
}

const CSS = `
.st{--bg:#f8fafc;--card:#fff;--text:#0f172a;--muted:#64748b;--line:#e2e8f0;--ok:#15803d;--ok-bg:#dcfce7;--warn:#b45309;--warn-bg:#fef3c7;--bad:#b91c1c;--bad-bg:#fee2e2;--off:#475569;--off-bg:#e2e8f0;
  max-width:640px;margin:0 auto;padding:32px 16px 112px;color:var(--text)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .st{--bg:#0b1220;--card:#111a2e;--text:#e2e8f0;--muted:#94a3b8;--line:#223049;--ok:#4ade80;--ok-bg:#12301f;--warn:#fbbf24;--warn-bg:#3a2a0a;--bad:#f87171;--bad-bg:#3b1414;--off:#cbd5e1;--off-bg:#1e293b}}
[data-theme="dark"] .st{--bg:#0b1220;--card:#111a2e;--text:#e2e8f0;--muted:#94a3b8;--line:#223049;--ok:#4ade80;--ok-bg:#12301f;--warn:#fbbf24;--warn-bg:#3a2a0a;--bad:#f87171;--bad-bg:#3b1414;--off:#cbd5e1;--off-bg:#1e293b}
.st-head{margin-bottom:24px}
.st-eyebrow{font-size:.8rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 4px}
.st-head h1{font-size:1.75rem;line-height:1.15;margin:0}
.st-banner{display:flex;align-items:center;gap:14px;padding:18px 20px;border-radius:16px;margin-bottom:20px}
.st-banner div{display:flex;flex-direction:column;gap:2px}
.st-banner strong{font-size:1.125rem}
.st-banner span:not(.st-dot){font-size:.875rem;opacity:.8}
.st-banner .st-dot{width:14px;height:14px;flex:none}
.st-banner.st-operational{background:var(--ok-bg);color:var(--ok)}
.st-banner.st-degraded,.st-banner.st-unknown{background:var(--warn-bg);color:var(--warn)}
.st-banner.st-outage{background:var(--bad-bg);color:var(--bad)}
.st-list{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.st-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px;border-bottom:1px solid var(--line)}
.st-row:last-child{border-bottom:0}
.st-row>div{display:flex;flex-direction:column;gap:2px;min-width:0}
.st-name{font-weight:600}
.st-note{font-size:.875rem;color:var(--muted)}
.st-pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;font-size:.875rem;font-weight:600;white-space:nowrap}
.st-pill.st-operational{background:var(--ok-bg);color:var(--ok)}
.st-pill.st-degraded{background:var(--warn-bg);color:var(--warn)}
.st-pill.st-outage{background:var(--bad-bg);color:var(--bad)}
.st-pill.st-unknown{background:var(--off-bg);color:var(--off)}
.st-dot{width:8px;height:8px;border-radius:50%;background:currentColor;display:inline-block}
.st-operational .st-dot{animation:st-pulse 2.4s ease-in-out infinite}
@keyframes st-pulse{0%,100%{opacity:1}50%{opacity:.35}}
@media (prefers-reduced-motion:reduce){.st-operational .st-dot{animation:none}}
.st-foot{margin-top:20px;display:flex;flex-direction:column;gap:12px;align-items:flex-start}
.st-foot p{margin:0;font-size:.875rem;color:var(--muted);max-width:52ch}
.st-refresh{display:inline-flex;align-items:center;min-height:44px;padding:0 18px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--text);font-weight:600;text-decoration:none}
@media (max-width:420px){.st-row{flex-direction:column;align-items:flex-start}}
`;

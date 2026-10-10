"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { bizRpc } from "@/app/biz-actions";
import { parseAmount, rub } from "@/lib/money";

export type FinanceEntry = { id: number; kind: string; amount: number; title: string; worker: string | null; date: string };
export type EstimateItem = { id: number; title: string; qty: number; unit: string; price: number };
export type WorkerOption = { id: number; name: string };

const KINDS = [
  { value: "expense", label: "🧱 Расход" },
  { value: "advance", label: "💵 Аванс от заказчика" },
  { value: "salary", label: "👷 Зарплата" },
];

export default function FinanceManager({
  siteId,
  workers,
  entries,
  estimateItems,
}: {
  siteId: number;
  workers: WorkerOption[];
  entries: FinanceEntry[];
  estimateItems: EstimateItem[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [kind, setKind] = useState("expense");
  const [amount, setAmount] = useState("");
  const [title, setTitle] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [date, setDate] = useState("");

  const [eTitle, setETitle] = useState("");
  const [eQty, setEQty] = useState("1");
  const [eUnit, setEUnit] = useState("");
  const [ePrice, setEPrice] = useState("");

  async function run(fn: string, args: Record<string, unknown>): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      const res = await bizRpc(fn, args);
      if (res.error) {
        setError(res.error);
        setBusy(false);
        return false;
      }
      router.refresh();
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
      setBusy(false);
      return false;
    }
    setBusy(false);
    return true;
  }

  async function addEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ok = await run("add_finance_entry", {
      p_site: siteId,
      p_kind: kind,
      p_amount: parseAmount(amount),
      p_title: title,
      p_worker: kind === "salary" && workerId ? Number(workerId) : null,
      p_date: date || null,
    });
    if (ok) {
      setAmount("");
      setTitle("");
    }
  }

  async function addItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ok = await run("add_estimate_item", {
      p_site: siteId,
      p_title: eTitle,
      p_qty: parseAmount(eQty),
      p_unit: eUnit,
      p_price: parseAmount(ePrice),
    });
    if (ok) {
      setETitle("");
      setEQty("1");
      setEUnit("");
      setEPrice("");
    }
  }

  async function removeEntry(id: number) {
    if (confirm("Удалить запись?")) await run("delete_finance_entry", { p_id: id });
  }

  async function removeItem(id: number) {
    if (confirm("Удалить позицию сметы?")) await run("delete_estimate_item", { p_id: id });
  }

  return (
    <>
      <h2>Новая запись</h2>
      <form className="actions" onSubmit={addEntry}>
        <div className="chips">
          {KINDS.map((k) => (
            <button key={k.value} type="button" className={kind === k.value ? "chip active" : "chip"} onClick={() => setKind(k.value)}>{k.label}</button>
          ))}
        </div>
        <input inputMode="decimal" placeholder="Сумма, ₽" value={amount} onChange={(e) => setAmount(e.target.value)} />
        {kind === "salary" ? (
          <select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
            <option value="">Выберите рабочего</option>
            {workers.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        ) : (
          <input placeholder={kind === "advance" ? "Комментарий (например, этап 1)" : "На что потрачено"} value={title} onChange={(e) => setTitle(e.target.value)} />
        )}
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Дата" />
        <button className="button" disabled={busy || !amount}>Добавить</button>
      </form>

      <h2>Записи ({entries.length})</h2>
      {!entries.length && <p className="muted">Записей пока нет.</p>}
      <div className="list">
        {entries.map((e) => (
          <div key={e.id} className="row row-flex">
            <span>
              <b>{e.kind === "advance" ? "+" : "−"}{rub(e.amount)}</b>{" "}
              {KINDS.find((k) => k.value === e.kind)?.label}
              <br />
              <span className="muted">{e.worker ? `${e.worker} · ` : ""}{e.title ? `${e.title} · ` : ""}{e.date}</span>
            </span>
            <button type="button" className="button small secondary" disabled={busy} onClick={() => removeEntry(e.id)} aria-label="Удалить запись">✕</button>
          </div>
        ))}
      </div>

      <h2>Смета</h2>
      <div className="list">
        {!estimateItems.length && <p className="muted">Позиций пока нет. Смету увидит заказчик по своей ссылке.</p>}
        {estimateItems.map((i) => (
          <div key={i.id} className="row row-flex">
            <span>
              <b>{i.title}</b>
              <br />
              <span className="muted">{i.qty} {i.unit} × {rub(i.price)} = {rub(i.qty * i.price)}</span>
            </span>
            <button type="button" className="button small secondary" disabled={busy} onClick={() => removeItem(i.id)} aria-label="Удалить позицию">✕</button>
          </div>
        ))}
      </div>
      <form className="actions" onSubmit={addItem}>
        <input placeholder="Позиция сметы" value={eTitle} onChange={(e) => setETitle(e.target.value)} />
        <input inputMode="decimal" placeholder="Количество" value={eQty} onChange={(e) => setEQty(e.target.value)} />
        <input placeholder="Ед. изм. (м², шт.)" value={eUnit} maxLength={20} onChange={(e) => setEUnit(e.target.value)} />
        <input inputMode="decimal" placeholder="Цена за единицу, ₽" value={ePrice} onChange={(e) => setEPrice(e.target.value)} />
        <button className="button secondary" disabled={busy || !eTitle || !ePrice}>Добавить в смету</button>
      </form>
      {error && <p className="notice">{error}</p>}
    </>
  );
}

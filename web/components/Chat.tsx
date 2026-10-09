"use client";

import "./chat.css";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { loadChat, sendChat } from "@/app/actions";
import { KIND_LABEL, formatTime } from "@/lib/chat";
import type { ChatKind, ChatMessage } from "@/lib/chat";

type TaskOption = { id: number; title: string };

const KINDS: { value: ChatKind; label: string }[] = [
  { value: "message", label: "Сообщение" },
  { value: "buy", label: "🛒 Купить" },
  { value: "problem", label: "⚠️ Проблема" },
];

export default function Chat({
  siteId,
  meId,
  initial,
  tasks,
}: {
  siteId: number;
  meId: number;
  initial: ChatMessage[];
  tasks: TaskOption[];
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(initial);
  const [text, setText] = useState("");
  const [kind, setKind] = useState<ChatKind>("message");
  const [taskId, setTaskId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const lastId = useRef(initial.length ? initial[initial.length - 1].id : 0);
  const stick = useRef(true);

  const poll = useCallback(async () => {
    try {
      const res = await loadChat(siteId, lastId.current);
      if (res.error || !res.messages.length) return;
      setMessages((prev) => {
        const known = new Set(prev.map((m) => m.id));
        const fresh = res.messages.filter((m) => !known.has(m.id));
        return fresh.length ? [...prev, ...fresh] : prev;
      });
    } catch {
      // Temporary network problem: the next poll retries.
    }
  }, [siteId]);

  useEffect(() => {
    if (messages.length) lastId.current = messages[messages.length - 1].id;
    const el = listRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") poll();
    }, 5000);
    return () => clearInterval(timer);
  }, [poll]);

  function onScroll() {
    const el = listRef.current;
    if (!el) return;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await sendChat({ siteId, text: value, kind, taskId: taskId ? Number(taskId) : null });
      if (res.error) {
        setError(res.error);
      } else {
        setText("");
        setKind("message");
        setTaskId("");
        stick.current = true;
        await poll();
      }
    } catch {
      setError("Нет связи с сервером. Повторите попытку.");
    }
    setBusy(false);
  }

  return (
    <div className="chat">
      <div className="chat-list" ref={listRef} onScroll={onScroll}>
        {!messages.length && <p className="muted">Сообщений пока нет. Напишите первым: что нужно купить или где проблема.</p>}
        {messages.map((m) => {
          const mine = m.user_id === meId;
          const body = m.body || (m.has_photo ? "📷 Фото (отправлено в Telegram)" : "");
          return (
            <div key={m.id} className={mine ? "msg mine" : "msg"}>
              {!mine && <div className="msg-author">{m.author_name}</div>}
              {KIND_LABEL[m.kind] && <span className={`msg-tag ${m.kind}`}>{KIND_LABEL[m.kind]}</span>}
              {body && <div className="msg-text">{body}</div>}
              {m.task_id && (
                <Link className="msg-task" href={`/tasks/${m.task_id}`}>📎 Задача: {m.task_title ?? `#${m.task_id}`}</Link>
              )}
              <div className="msg-meta" suppressHydrationWarning>{formatTime(m.sent_at)}</div>
            </div>
          );
        })}
      </div>

      <form className="composer" onSubmit={submit}>
        <div className="chips">
          {KINDS.map((k) => (
            <button key={k.value} type="button" className={kind === k.value ? "chip active" : "chip"} onClick={() => setKind(k.value)}>
              {k.label}
            </button>
          ))}
        </div>
        {tasks.length > 0 && (
          <select value={taskId} onChange={(e) => setTaskId(e.target.value)} aria-label="Прикрепить задачу">
            <option value="">Без задачи</option>
            {tasks.map((t) => <option key={t.id} value={t.id}>📎 {t.title}</option>)}
          </select>
        )}
        <div className="composer-row">
          <textarea
            rows={1}
            value={text}
            maxLength={2000}
            placeholder={kind === "buy" ? "Что нужно купить…" : kind === "problem" ? "Опишите проблему…" : "Сообщение…"}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="button" disabled={busy || !text.trim()}>{busy ? "…" : "Отправить"}</button>
        </div>
        {error && <p className="notice">{error}</p>}
      </form>
    </div>
  );
}

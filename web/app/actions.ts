"use server";

import { createClient } from "@/lib/supabase/server";
import { explain } from "@/lib/errors";
import { KIND_LABEL } from "@/lib/chat";
import type { ChatMessage } from "@/lib/chat";

const ALLOWED = new Set([
  "create_site", "update_site", "regenerate_invite", "delete_site", "remove_member",
  "create_task", "update_task", "assign_task", "take_task", "submit_task",
  "review_task", "release_task", "reopen_task", "delete_task",
  "create_pwa_profile", "link_telegram_account", "join_site",
  "update_my_profile", "create_telegram_connect_code", "set_notifications",
]);

const MAX_PHOTO_BYTES = 4 * 1024 * 1024;
const MAX_AVATAR_BYTES = 2 * 1024 * 1024;
const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

export async function rpcAction(
  fn: string,
  args: Record<string, unknown>,
): Promise<{ data: unknown; error: string | null }> {
  if (!ALLOWED.has(fn)) return { data: null, error: "Недопустимое действие." };

  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { data: null, error: explain("not authenticated") };

  const { data, error } = await supabase.rpc(fn, args);
  if (error) return { data: null, error: explain(error.message) };
  return { data, error: null };
}

export async function uploadTaskPhoto(
  formData: FormData,
): Promise<{ path: string | null; error: string | null }> {
  const taskId = Number(formData.get("taskId"));
  const file = formData.get("file");
  if (!Number.isInteger(taskId) || !(file instanceof File)) {
    return { path: null, error: "Неверные данные фото." };
  }
  if (file.size > MAX_PHOTO_BYTES) return { path: null, error: "Фото слишком большое (максимум 4 МБ)." };
  if (!PHOTO_TYPES.includes(file.type)) return { path: null, error: "Допустимы только JPG, PNG и WebP." };

  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { path: null, error: explain("not authenticated") };

  const ext = file.type === "image/png" ? "png" : file.type === "image/webp" ? "webp" : "jpg";
  const path = `${taskId}/${Date.now()}-${Math.random().toString(36).slice(2, 10)}.${ext}`;

  const { error } = await supabase.storage
    .from("task-photos")
    .upload(path, file, { contentType: file.type, upsert: false });
  if (error) {
    const denied = /row-level security|not allowed|unauthorized/i.test(error.message);
    return { path: null, error: denied ? "Нельзя загрузить фото: задача не ваша или не в работе." : error.message };
  }
  return { path, error: null };
}

export async function uploadAvatar(formData: FormData): Promise<{ error: string | null }> {
  const file = formData.get("file");
  if (!(file instanceof File)) return { error: "Неверные данные фото." };
  if (file.size > MAX_AVATAR_BYTES) return { error: "Фото слишком большое (максимум 2 МБ)." };
  if (!PHOTO_TYPES.includes(file.type)) return { error: "Допустимы только JPG, PNG и WebP." };

  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: explain("not authenticated") };

  const { data } = await supabase.from("users").select("id, avatar_path").eq("auth_id", user.id).maybeSingle();
  const me = data as unknown as { id: number; avatar_path: string | null } | null;
  if (!me) return { error: "Профиль не найден. Убедитесь, что выполнен SQL-файл supabase_pwa_profile.sql." };

  const path = `${me.id}/${Date.now()}.jpg`;
  const { error: uploadError } = await supabase.storage
    .from("avatars")
    .upload(path, file, { contentType: file.type, upsert: false });
  if (uploadError) return { error: uploadError.message };

  const { error } = await supabase.rpc("set_avatar", { p_path: path });
  if (error) return { error: explain(error.message) };

  if (me.avatar_path) await supabase.storage.from("avatars").remove([me.avatar_path]);
  return { error: null };
}

export async function removeAvatar(): Promise<{ error: string | null }> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: explain("not authenticated") };

  const { data } = await supabase.from("users").select("avatar_path").eq("auth_id", user.id).maybeSingle();
  const old = (data as unknown as { avatar_path: string | null } | null)?.avatar_path ?? null;

  const { error } = await supabase.rpc("set_avatar", { p_path: null });
  if (error) return { error: explain(error.message) };
  if (old) await supabase.storage.from("avatars").remove([old]);
  return { error: null };
}

export async function loadChat(
  siteId: number,
  afterId: number,
): Promise<{ messages: ChatMessage[]; error: string | null }> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { messages: [], error: explain("not authenticated") };

  const { data, error } = await supabase.rpc("get_chat", { p_site: siteId, p_after: afterId });
  if (error) return { messages: [], error: explain(error.message) };
  return { messages: (data ?? []) as unknown as ChatMessage[], error: null };
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

type NotifyTarget = {
  chat_id: number;
  site_name: string;
  author: string;
  body: string;
  kind: string;
  task_title: string | null;
};

async function notifyTelegram(
  supabase: ReturnType<typeof createClient>,
  messageId: number,
): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) return;

  const { data } = await supabase.rpc("chat_notify_targets", { p_message: messageId });
  const targets = (data ?? []) as unknown as NotifyTarget[];

  await Promise.allSettled(
    targets.map((t) => {
      const lines = [`💬 <b>${escapeHtml(t.site_name)}</b>`];
      if (KIND_LABEL[t.kind]) lines.push(KIND_LABEL[t.kind]);
      lines.push(`<b>${escapeHtml(t.author)}:</b> ${escapeHtml(t.body)}`);
      if (t.task_title) lines.push(`📎 Задача: ${escapeHtml(t.task_title)}`);

      return fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: t.chat_id,
          text: lines.join("\n"),
          parse_mode: "HTML",
          disable_web_page_preview: true,
        }),
        signal: AbortSignal.timeout(4000),
      });
    }),
  );
}

export async function sendChat(input: {
  siteId: number;
  text: string;
  kind: string;
  taskId: number | null;
}): Promise<{ error: string | null }> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { error: explain("not authenticated") };

  const { data, error } = await supabase.rpc("send_chat_message", {
    p_site: input.siteId,
    p_text: input.text,
    p_kind: input.kind,
    p_task: input.taskId,
  });
  if (error) return { error: explain(error.message) };

  try {
    await notifyTelegram(supabase, Number(data));
  } catch {
    // The message is saved; a failed Telegram notification must not break sending.
  }
  return { error: null };
}

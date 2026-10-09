"use server";

import { createClient } from "@/lib/supabase/server";
import { explain } from "@/lib/errors";

const ALLOWED = new Set([
  "create_site", "update_site", "regenerate_invite", "delete_site", "remove_member",
  "create_task", "update_task", "assign_task", "take_task", "submit_task",
  "review_task", "release_task", "reopen_task", "delete_task",
  "create_pwa_profile", "link_telegram_account", "join_site",
]);

const MAX_PHOTO_BYTES = 4 * 1024 * 1024;
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

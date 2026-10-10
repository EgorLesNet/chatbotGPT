import { randomUUID } from "crypto";

export const PRICE_RUB = 500;
export const PERIOD_DAYS = 30;
const API = "https://api.yookassa.ru/v3";

function authHeader(): string | null {
  const shop = process.env.YOOKASSA_SHOP_ID;
  const key = process.env.YOOKASSA_SECRET_KEY;
  if (!shop || !key) return null;
  return "Basic " + Buffer.from(`${shop}:${key}`).toString("base64");
}

export async function createYooPayment(
  userId: number,
  returnUrl: string,
): Promise<{ id: string; url: string } | { error: string }> {
  const auth = authHeader();
  if (!auth) return { error: "Оплата ещё не настроена: нет ключей ЮKassa." };

  const res = await fetch(`${API}/payments`, {
    method: "POST",
    headers: { Authorization: auth, "Idempotence-Key": randomUUID(), "Content-Type": "application/json" },
    body: JSON.stringify({
      amount: { value: `${PRICE_RUB}.00`, currency: "RUB" },
      capture: true,
      confirmation: { type: "redirect", return_url: returnUrl },
      description: `Подписка прораба на ${PERIOD_DAYS} дней: более 3 объектов`,
      metadata: { user_id: String(userId) },
    }),
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) return { error: "Не удалось создать платёж. Попробуйте позже." };

  const json = await res.json();
  const url = json?.confirmation?.confirmation_url;
  if (!json?.id || !url) return { error: "Не удалось создать платёж. Попробуйте позже." };
  return { id: String(json.id), url: String(url) };
}

async function confirmPaid(externalId: string, userId: number, amount: number): Promise<boolean> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return false;

  const res = await fetch(`${url}/rest/v1/rpc/confirm_payment`, {
    method: "POST",
    headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ p_external_id: externalId, p_user: userId, p_amount: amount }),
    signal: AbortSignal.timeout(8000),
  });
  return res.ok;
}

// Never trust the webhook body: re-read the payment from YooKassa with our own credentials.
// Safe to call repeatedly: the database extends the subscription only once per payment.
export async function verifyAndConfirm(externalId: string): Promise<boolean> {
  const auth = authHeader();
  if (!auth || !externalId) return false;

  const res = await fetch(`${API}/payments/${encodeURIComponent(externalId)}`, {
    headers: { Authorization: auth },
    signal: AbortSignal.timeout(8000),
    cache: "no-store",
  });
  if (!res.ok) return false;

  const p = await res.json();
  const amount = Number(p?.amount?.value);
  const userId = Number(p?.metadata?.user_id);
  const valid =
    p?.status === "succeeded" &&
    p?.paid === true &&
    p?.amount?.currency === "RUB" &&
    amount >= PRICE_RUB &&
    Number.isInteger(userId) &&
    userId > 0;
  if (!valid) return false;

  return confirmPaid(externalId, userId, amount);
}

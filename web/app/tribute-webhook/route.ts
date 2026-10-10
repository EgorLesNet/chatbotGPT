import { createHmac, timingSafeEqual } from "crypto";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// NOTE: vercel.json rewrites /api/* to the Python bot service, so this route must live outside /api.
const HANDLED = new Set(["new_subscription", "renewed_subscription", "cancelled_subscription"]);
const MIN_PRICE_KOPECKS = 50000;

export async function GET() {
  return NextResponse.json({ status: "tribute webhook is up" });
}

export async function POST(req: Request) {
  const apiKey = process.env.TRIBUTE_API_KEY;
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!apiKey || !supabaseUrl || !serviceKey) {
    return NextResponse.json({ error: "not configured" }, { status: 503 });
  }

  const raw = await req.text();
  const signature = (req.headers.get("trbt-signature") ?? "").trim().toLowerCase();
  const expected = createHmac("sha256", apiKey.trim()).update(raw).digest("hex");
  const a = Buffer.from(signature);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    return NextResponse.json({ error: "invalid signature" }, { status: 401 });
  }

  let evt: { name?: string; payload?: Record<string, unknown> };
  try {
    evt = JSON.parse(raw);
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }

  const name = String(evt?.name ?? "");
  const p = (evt?.payload ?? {}) as Record<string, unknown>;
  if (!HANDLED.has(name)) return NextResponse.json({ status: "ignored" });

  const wantedId = process.env.TRIBUTE_SUBSCRIPTION_ID;
  if (wantedId && String(p.subscription_id) !== wantedId) {
    return NextResponse.json({ status: "ignored" });
  }
  if (String(p.currency ?? "").toLowerCase() !== "rub" || Number(p.price) < MIN_PRICE_KOPECKS) {
    return NextResponse.json({ status: "ignored" });
  }

  const tg = Number(p.telegram_user_id);
  const expiresMs = Date.parse(String(p.expires_at ?? ""));
  if (!Number.isFinite(tg) || tg <= 0 || !Number.isFinite(expiresMs)) {
    return NextResponse.json({ error: "bad payload" }, { status: 400 });
  }

  const key = [name, p.subscription_id, p.period_id, tg, p.expires_at].join(":");
  const res = await fetch(`${supabaseUrl}/rest/v1/rpc/apply_tribute_event`, {
    method: "POST",
    headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      p_key: key,
      p_name: name,
      p_tg: tg,
      p_expires: new Date(expiresMs).toISOString(),
      p_payload: p,
    }),
    signal: AbortSignal.timeout(8000),
  });

  if (!res.ok) return NextResponse.json({ error: "storage error" }, { status: 500 });
  return NextResponse.json({ status: "ok" });
}

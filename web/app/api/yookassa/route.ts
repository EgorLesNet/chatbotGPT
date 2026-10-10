import { NextResponse } from "next/server";
import { verifyAndConfirm } from "@/lib/billing";

export const dynamic = "force-dynamic";

// YooKassa notification URL: https://<your-domain>/api/yookassa (event: payment.succeeded).
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const id = body?.object?.id;
    if (body?.event === "payment.succeeded" && typeof id === "string") {
      await verifyAndConfirm(id);
    }
  } catch {
    // Malformed body: nothing to do. Always answer 200 so YooKassa does not retry endlessly.
  }
  return NextResponse.json({ ok: true });
}

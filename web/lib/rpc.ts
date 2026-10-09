import { rpcAction } from "@/app/actions";

export async function callRpcData(
  fn: string,
  args: Record<string, unknown>,
): Promise<{ data: unknown; error: string | null }> {
  try {
    return await rpcAction(fn, args);
  } catch {
    return { data: null, error: "Нет связи с сервером. Проверьте интернет и повторите." };
  }
}

/** Returns an error text for the user, or null on success. */
export async function callRpc(fn: string, args: Record<string, unknown>): Promise<string | null> {
  return (await callRpcData(fn, args)).error;
}

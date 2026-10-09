import { rpcAction, uploadTaskPhoto } from "@/app/actions";

const NO_CONNECTION = "Нет связи с сервером. Проверьте интернет и повторите.";

export async function callRpcData(
  fn: string,
  args: Record<string, unknown>,
): Promise<{ data: unknown; error: string | null }> {
  try {
    return await rpcAction(fn, args);
  } catch {
    return { data: null, error: NO_CONNECTION };
  }
}

/** Returns an error text for the user, or null on success. */
export async function callRpc(fn: string, args: Record<string, unknown>): Promise<string | null> {
  return (await callRpcData(fn, args)).error;
}

export async function uploadPhoto(
  taskId: number,
  file: File,
): Promise<{ path: string | null; error: string | null }> {
  const formData = new FormData();
  formData.append("taskId", String(taskId));
  formData.append("file", file);
  try {
    return await uploadTaskPhoto(formData);
  } catch {
    return { path: null, error: NO_CONNECTION };
  }
}

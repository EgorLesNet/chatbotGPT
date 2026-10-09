type AuthError = { message: string; code?: string; name?: string };
type Result<T> = Promise<{ data: T | null; error: AuthError | null }>;

export type PasskeyItem = {
  id: string;
  friendly_name?: string;
  created_at: string;
  last_used_at?: string;
};

export type PasskeyAuth = {
  registerPasskey: () => Result<{ id: string }>;
  signInWithPasskey: () => Result<unknown>;
  passkey: {
    list: () => Result<PasskeyItem[]>;
    delete: (args: { passkeyId: string }) => Result<unknown>;
  };
};

/** Returns the passkey API, or null when the installed supabase-js has no passkey support. */
export function passkeyAuth(client: { auth: unknown }): PasskeyAuth | null {
  const auth = client.auth as Partial<PasskeyAuth>;
  if (typeof auth.signInWithPasskey !== "function" || typeof auth.registerPasskey !== "function" || !auth.passkey) {
    return null;
  }
  return auth as PasskeyAuth;
}

export function passkeySupported(): boolean {
  return typeof window !== "undefined" && typeof window.PublicKeyCredential !== "undefined";
}

export function passkeyMessage(error: AuthError): string {
  const text = `${error.code ?? ""} ${error.name ?? ""} ${error.message}`;
  if (/passkey_disabled/i.test(text)) return "Passkey не включены в Supabase (Authentication → Passkeys).";
  if (/webauthn_credential_exists/i.test(text)) return "Это устройство уже добавлено.";
  if (/too_many_passkeys/i.test(text)) return "Достигнут лимит passkey на аккаунт. Удалите лишние.";
  if (/webauthn_credential_not_found/i.test(text)) return "Этот passkey не найден. Войдите по паролю и добавьте его заново.";
  if (/email_not_confirmed/i.test(text)) return "Подтвердите email по письму.";
  if (/NotAllowedError|cancel|abort|timed out/i.test(text)) return "Операция отменена или время истекло.";
  if (/SecurityError|rp id|relying party|origin/i.test(text)) return "Неверный Relying Party ID или Origin в настройках Supabase: они должны совпадать с адресом сайта.";
  return error.message;
}

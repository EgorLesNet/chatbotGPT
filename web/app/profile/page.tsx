import { cookies } from "next/headers";
import { getProfile } from "@/lib/profile";
import AvatarEditor from "@/components/AvatarEditor";
import ProfileForm from "@/components/ProfileForm";
import ThemeSwitcher from "@/components/ThemeSwitcher";
import TelegramConnect from "@/components/TelegramConnect";
import PasskeySettings from "@/components/PasskeySettings";
import SignOut from "../dashboard/sign-out";

type Extra = { avatar_path: string | null; telegram_id: number | null; notifications: boolean };

export default async function ProfilePage() {
  const { supabase, profile } = await getProfile();

  const { data } = await supabase
    .from("users")
    .select("avatar_path, telegram_id, notifications")
    .eq("id", profile.id)
    .maybeSingle();
  const extra = data as unknown as Extra | null;

  const avatarPath = extra?.avatar_path ?? null;
  const avatarUrl = avatarPath
    ? `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/avatars/${avatarPath}`
    : null;

  const saved = cookies().get("theme")?.value;
  const theme = saved === "light" || saved === "dark" ? saved : "system";

  return (
    <main className="container">
      <section className="card">
        <p className="eyebrow">ПРОФИЛЬ</p>
        <h1>{profile.name}</h1>
        <p className="muted">Роль: {profile.role === "foreman" ? "прораб" : "рабочий"}</p>
        <AvatarEditor name={profile.name} url={avatarUrl} />
        <ProfileForm name={profile.name} role={profile.role} />
        <ThemeSwitcher initial={theme} />
        <TelegramConnect
          connected={extra?.telegram_id != null}
          notifications={extra?.notifications ?? true}
          botUsername={process.env.TELEGRAM_BOT_USERNAME ?? null}
        />
        <PasskeySettings />
        <SignOut />
      </section>
    </main>
  );
}

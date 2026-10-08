# Prorab PWA

PWA for foremen and workers. It shares the Supabase Postgres database with the Telegram bot.

## Local setup

```bash
cd web
cp .env.local.example .env.local
npm install
npm run dev
```

Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `web/.env.local`.

## Supabase setup

1. Run `supabase_pwa_migration.sql` in Supabase SQL Editor.
2. In **Authentication → Providers → Email**, enable email/password authentication.
3. For development, add `http://localhost:3000/**` to **Authentication → URL Configuration → Redirect URLs**.
4. After Vercel deployment, add `https://YOUR-APP.vercel.app/**` to the same Redirect URLs list.

## Vercel

Import this repository into Vercel. Set the **Root Directory** to `web` and add the same two public environment variables there.

import { Suspense } from "react";
import { AppShell, Section } from "@/components/app-shell";
import { TelegramConnect } from "@/components/settings/telegram-connect";
import { CityPicker } from "@/components/settings/city-picker";
import { PreferencesForm } from "@/components/settings/preferences-form";
import { requireUser } from "@/lib/auth/session";
import { loadUserSetup } from "@/lib/settings/queries";

async function Body() {
  const { supabase, user } = await requireUser();
  const { cities, prefs, telegramLinked } = await loadUserSetup(supabase, user.id);
  return (
    <>
      <Section title="Cities" hint="We only alert you about shows in these cities."><CityPicker selected={cities} /></Section>
      <Section title="Notifications"><PreferencesForm prefs={prefs} /></Section>
      <Section title="Telegram" hint="Alerts are sent to your Telegram chat. Linking uses a single-use link and never shares your account details.">
        <TelegramConnect configured={!!process.env.TELEGRAM_BOT_USERNAME} connected={telegramLinked} />
      </Section>
      <Section title="Account"><p className="text-mist">Signed in as {user.email}</p></Section>
    </>
  );
}

export default function SettingsPage() {
  return (
    <AppShell title="Settings">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </AppShell>
  );
}

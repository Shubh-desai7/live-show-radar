"use client";

import { useActionState } from "react";
import { savePreferences, type SettingsState } from "@/lib/settings/actions";
import type { Prefs } from "@/lib/settings/queries";

const rows: { key: keyof Prefs; label: string; hint: string }[] = [
  { key: "new_event_alerts", label: "New concert announcements", hint: "When a followed artist announces a show in your cities." },
  { key: "presale_alerts", label: "Presale reminders", hint: "Registration deadlines and presale openings." },
  { key: "ticket_sale_alerts", label: "General sale reminders", hint: "When tickets open to everyone." },
  { key: "event_update_alerts", label: "Changes and cancellations", hint: "Date, venue or status changes." },
];

export function PreferencesForm({ prefs }: { prefs: Prefs }) {
  const [state, action, pending] = useActionState<SettingsState, FormData>(savePreferences, {});
  return (
    <form action={action} className="flex flex-col gap-4">
      {rows.map((r) => (
        <label key={r.key} className="flex items-start gap-3">
          <input type="checkbox" name={r.key} defaultChecked={prefs[r.key]} className="mt-1 size-5 accent-volt" />
          <span><span className="block font-bold">{r.label}</span><span className="text-sm text-mist">{r.hint}</span></span>
        </label>
      ))}
      <p className="text-sm text-mist">Alerts go to Telegram once you connect it. Sending alerts isn&apos;t switched on in this build yet, and delivery will never be instant.</p>
      <div className="flex items-center gap-4">
        <button disabled={pending} className="rounded-full bg-volt px-6 py-2 font-extrabold text-ink disabled:opacity-60">{pending ? "Saving…" : "Save"}</button>
        <p aria-live="polite" className="text-sm font-semibold text-volt">{state.message}<span className="text-hotpink">{state.error}</span></p>
      </div>
    </form>
  );
}

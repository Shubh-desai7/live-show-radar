import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
import { requireAdmin } from "@/lib/auth/session";

type Stats = Record<string, unknown>;

function host(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return "source"; }
}

async function Body() {
  const { admin } = await requireAdmin();
  const count = async (table: string, f?: (q: any) => any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
    const q = admin.from(table).select("*", { count: "exact", head: true });
    return (f ? await f(q) : await q).count ?? 0;
  };
  const today = new Date().toISOString().slice(0, 10);
  const [catalog, sources, upConf, upUnconf, retained, runsRes, resultsRes, reasonsRes] = await Promise.all([
    count("artists", (q) => q.eq("featured", true)),
    count("sources"),
    count("events", (q) => q.eq("confidence", "confirmed").gte("event_date", today)),
    count("events", (q) => q.eq("confidence", "unconfirmed").gte("event_date", today)),
    count("event_candidates", (q) => q.eq("status", "open")),
    admin.from("discovery_runs").select("run_id, command, trigger, started_at, finished_at, ok, error, stats").order("started_at", { ascending: false }).limit(10),
    admin.from("discovery_source_results").select("source_url, status, detail, candidates, rejected, events_new").order("id", { ascending: false }).limit(40),
    admin.from("event_candidates").select("reason").eq("status", "open").limit(2000),
  ]);
  const reasons = new Map<string, number>();
  for (const r of reasonsRes.data ?? []) reasons.set(r.reason as string, (reasons.get(r.reason as string) ?? 0) + 1);
  const runs = runsRes.data ?? [];
  return (
    <div className="space-y-8">
      <p className="text-mist">Admin only. Hosts are shown, never credentials or page content.</p>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {[["Catalog artists", catalog], ["Sources", sources], ["Upcoming confirmed", upConf], ["Upcoming unconfirmed", upUnconf], ["Retained candidates", retained]].map(([k, v]) => (
          <div key={k as string} className="rounded-2xl border border-line p-4"><dt className="text-sm text-mist">{k}</dt><dd className="font-display text-3xl">{v as number}</dd></div>
        ))}
      </dl>
      <section>
        <h2 className="font-display text-2xl">Recent runs</h2>
        {runs.length === 0 && <p className="text-mist">No runs recorded yet.</p>}
        <ul className="mt-3 space-y-2">
          {runs.map((r) => {
            const s = (r.stats ?? {}) as Stats;
            return (
              <li key={r.run_id as string} className="rounded-xl border border-line p-3 text-sm">
                <b>{r.command as string}</b> via {r.trigger as string} · {new Date(r.started_at as string).toISOString().replace("T", " ").slice(0, 16)} UTC · {r.ok ? "ok" : `failed: ${String(r.error ?? "").slice(0, 80)}`}
                <div className="text-mist">{["sources_attempted", "sources_fetched", "sources_blocked", "sources_unchanged", "candidates_extracted", "events_created_confirmed", "events_created_unconfirmed", "duplicates_ignored"].map((k) => `${k.replace(/_/g, " ")}: ${String(s[k] ?? 0)}`).join(" · ")}</div>
              </li>
            );
          })}
        </ul>
      </section>
      <section>
        <h2 className="font-display text-2xl">Why candidates were kept back</h2>
        <ul className="mt-3 flex flex-wrap gap-2 text-sm">
          {[...reasons.entries()].sort((a, b) => b[1] - a[1]).map(([k, v]) => <li key={k} className="rounded-full border border-line px-3 py-1">{k.replace(/_/g, " ")} · {v}</li>)}
          {reasons.size === 0 && <li className="text-mist">None yet.</li>}
        </ul>
      </section>
      <section>
        <h2 className="font-display text-2xl">Latest source results</h2>
        <ul className="mt-3 space-y-1 text-sm">
          {(resultsRes.data ?? []).map((r, i) => (
            <li key={i}>{host(r.source_url as string)} · {r.status as string} · candidates {r.candidates as number} · rejected {r.rejected as number} · new {r.events_new as number}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default function DiagnosticsPage() {
  return (
    <AppShell title="Discovery diagnostics">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </AppShell>
  );
}

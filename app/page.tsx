import Link from "next/link";
import { BellRing, Radar, ShieldCheck } from "lucide-react";
import { ConcertCard } from "@/components/events/concert-card";

const pillars = [
  { icon: Radar, title: "Follow your artists", body: "Pick who you love and the Indian cities you'll travel to. We watch official and public sources for you." },
  { icon: ShieldCheck, title: "Know what's real", body: "Every show shows its source and status: confirmed, or clearly unconfirmed. Rumours never get passed off as events." },
  { icon: BellRing, title: "Never miss a deadline", body: "Presale and sale reminders land 24 hours and 2 hours ahead, whenever the timing is reliable." },
];

export default function Home() {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-24 px-5 py-10 md:px-8">
      <header className="flex items-center justify-between">
        <span className="font-display text-xl font-extrabold tracking-tight">
          live show <span className="text-volt">radar</span>
        </span>
        <Link href="/login" className="rounded-full border border-line px-4 py-2 text-sm font-semibold">
          Log in
        </Link>
      </header>

      <section className="grid items-center gap-12 md:grid-cols-[1.2fr_1fr]">
        <div className="flex flex-col gap-6">
          <h1 className="font-display text-6xl font-extrabold leading-[0.9] tracking-tighter md:text-8xl">
            Zero <span className="text-volt">missed</span> shows.
          </h1>
          <p className="max-w-xl text-lg text-mist">
            Follow the artists you love. Get alerted the moment a show is announced in your city, and again before every presale and sale deadline.
          </p>
          <Link href="/signup" className="w-fit rounded-full bg-volt px-8 py-4 text-lg font-extrabold text-ink">
            Get started
          </Link>
        </div>

        <div aria-label="Sample cards. Not real events." className="relative flex flex-col gap-4">
          <span className="w-fit -rotate-2 rounded-md bg-acid px-2 py-1 text-xs font-extrabold uppercase text-ink">Sample preview, not real events</span>
          <ConcertCard artist="Artist Name" city="Bengaluru" date="Date TBA" confidence="confirmed" highlight="Presale soon" tone="grape" className="-rotate-2" />
          <ConcertCard artist="Another Artist" city="Mumbai" date="Date TBA" confidence="unconfirmed" tone="ember" className="ml-8 rotate-1" />
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-3">
        {pillars.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-3xl border border-line bg-ink-2 p-6">
            <Icon aria-hidden className="mb-4 size-8 text-volt" />
            <h2 className="font-display text-2xl font-extrabold">{title}</h2>
            <p className="mt-2 text-mist">{body}</p>
          </div>
        ))}
      </section>

      <footer className="border-t border-line pt-6 text-sm text-mist">
        Live Show Radar doesn&apos;t sell tickets. You always buy on the official ticketing site.
      </footer>
    </main>
  );
}

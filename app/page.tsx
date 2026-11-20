import { BellRing, Radar, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { ConcertCard } from "@/components/events/concert-card";
import { Backdrop } from "@/components/motion/backdrop";
import { Float } from "@/components/motion/float";
import { HeroTitle } from "@/components/motion/hero-title";
import { Magnetic } from "@/components/motion/magnetic";
import { Marquee } from "@/components/motion/marquee";
import { Reveal } from "@/components/motion/reveal";

const pillars = [
  { icon: Radar, title: "Follow your artists", body: "Pick who you love and the Indian cities you'll travel to. We watch official and public sources for you." },
  { icon: ShieldCheck, title: "Know what's real", body: "Every show shows its source and status: confirmed, or clearly unconfirmed. Rumours never get passed off as events." },
  { icon: BellRing, title: "Never miss a deadline", body: "Presale and sale reminders land 24 hours and 2 hours ahead, whenever the timing is reliable." },
];

const ticker = ["Arijit Singh", "Diljit Dosanjh", "A. R. Rahman", "Coldplay", "Ed Sheeran", "AP Dhillon", "Karan Aujla", "Taylor Swift",
  "Prateek Kuhad", "Anuv Jain", "Shreya Ghoshal", "Badshah", "Divine", "Imagine Dragons", "Dua Lipa", "Nucleya", "Ritviz"];

export default function Home() {
  return (
    <>
      <Backdrop />
      <main className="mx-auto flex max-w-6xl flex-col gap-20 px-5 py-10 md:px-8">
        <Reveal as="header" y={-18} className="flex items-center justify-between">
          <span className="font-display text-xl font-extrabold tracking-tight">
            live show <span className="text-volt">radar</span>
          </span>
          <Link href="/login" className="rounded-full border border-line px-4 py-2 text-sm font-semibold transition-colors hover:border-volt hover:text-volt">
            Log in
          </Link>
        </Reveal>

        <section className="grid items-center gap-12 md:grid-cols-[1.2fr_1fr]">
          <div className="flex flex-col gap-6">
            <HeroTitle className="font-display text-6xl font-extrabold leading-[0.9] tracking-tighter md:text-8xl" />
            <Reveal className="flex flex-col gap-6" delay={0.7} y={20}>
              <p className="max-w-xl text-lg text-mist">
                Follow the artists you love. Get alerted the moment a show is announced in your city, and again before every presale and sale deadline.
              </p>
              <Magnetic className="w-fit">
                <Link href="/signup" className="inline-block rounded-full bg-volt px-8 py-4 text-lg font-extrabold text-ink">
                  Get started
                </Link>
              </Magnetic>
            </Reveal>
          </div>

          <div aria-label="Sample cards. Not real events." className="relative flex flex-col gap-4">
            <span className="w-fit -rotate-2 rounded-md bg-acid px-2 py-1 text-xs font-extrabold uppercase text-ink">Sample preview, not real events</span>
            <Float amount={9}>
              <ConcertCard artist="Artist Name" city="Bengaluru" date="Date TBA" confidence="confirmed" highlight="Presale soon" tone="grape" className="-rotate-2" />
            </Float>
            <Float amount={12} delay={0.6} className="ml-8">
              <ConcertCard artist="Another Artist" city="Mumbai" date="Date TBA" confidence="unconfirmed" tone="ember" className="rotate-1" />
            </Float>
          </div>
        </section>

        <Marquee items={ticker} className="-mx-5 border-y border-line py-4 font-display text-3xl font-extrabold uppercase tracking-tight text-bone/80 md:-mx-8" />

        <Reveal as="section" scroll className="grid gap-5 md:grid-cols-3">
          {pillars.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-3xl border border-line bg-ink-2/80 p-6 backdrop-blur transition-colors hover:border-volt">
              <Icon aria-hidden className="mb-4 size-8 text-volt" />
              <h2 className="font-display text-2xl font-extrabold">{title}</h2>
              <p className="mt-2 text-mist">{body}</p>
            </div>
          ))}
        </Reveal>

        <footer className="border-t border-line pt-6 text-sm text-mist">
          Live Show Radar doesn&apos;t sell tickets. You always buy on the official ticketing site.
        </footer>
      </main>
    </>
  );
}

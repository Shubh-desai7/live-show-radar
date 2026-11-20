import Link from "next/link";
import { signOut } from "@/lib/auth/actions";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/artists", label: "Artists" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-6xl flex-col gap-8 px-5 py-8 md:px-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <Link href="/dashboard" className="font-display text-xl font-extrabold tracking-tight">
          live show <span className="text-volt">radar</span>
        </Link>
        <nav className="flex items-center gap-2 text-sm font-semibold">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="rounded-full px-4 py-2 hover:bg-ink-3">{l.label}</Link>
          ))}
          <form action={signOut}><button className="rounded-full border border-line px-4 py-2">Log out</button></form>
        </nav>
      </header>
      <h1 className="font-display text-5xl font-extrabold leading-none tracking-tighter md:text-7xl">{title}</h1>
      {children}
    </main>
  );
}

export function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4 rounded-3xl border border-line bg-ink-2 p-6">
      <div>
        <h2 className="font-display text-2xl font-extrabold">{title}</h2>
        {hint && <p className="text-mist">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

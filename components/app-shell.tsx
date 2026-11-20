import Link from "next/link";
import { Reveal } from "@/components/motion/reveal";
import { signOut } from "@/lib/auth/actions";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/artists", label: "Artists" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-6xl flex-col gap-8 px-5 py-8 md:px-8">
      <Reveal as="header" y={-18} stagger={0.1} className="flex flex-wrap items-center justify-between gap-4">
        <Link href="/dashboard" className="font-display text-xl font-extrabold tracking-tight">
          live show <span className="text-volt">radar</span>
        </Link>
        <nav className="flex items-center gap-2 text-sm font-semibold">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="rounded-full px-4 py-2 hover:bg-ink-3">{l.label}</Link>
          ))}
          <form action={signOut}><button className="rounded-full border border-line px-4 py-2">Log out</button></form>
        </nav>
      </Reveal>
      <Reveal y={40} delay={0.15}><h1 className="font-display text-5xl font-extrabold leading-none tracking-tighter md:text-7xl">{title}</h1></Reveal>
      {children}
    </main>
  );
}

export { Section } from "./section";

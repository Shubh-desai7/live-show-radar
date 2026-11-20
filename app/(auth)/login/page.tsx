import Link from "next/link";
import { AuthForm } from "@/components/auth/auth-form";

export default function Page() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-6xl flex-col gap-10 px-5 py-10 md:px-8">
      <Link href="/" className="font-display text-xl font-extrabold tracking-tight">
        live show <span className="text-volt">radar</span>
      </Link>
      <div className="flex flex-1 items-center justify-center pb-16">
        <AuthForm mode="login" />
      </div>
    </main>
  );
}

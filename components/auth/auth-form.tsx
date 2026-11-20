"use client";

import Link from "next/link";
import { useActionState } from "react";
import { signIn, signUp, type AuthState } from "@/lib/auth/actions";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const [state, action, pending] = useActionState<AuthState, FormData>(mode === "login" ? signIn : signUp, {});
  const isLogin = mode === "login";
  const field = "w-full rounded-xl border border-line bg-ink-2 px-4 py-3 text-bone placeholder:text-mist";

  return (
    <form action={action} className="flex w-full max-w-md flex-col gap-4 rounded-3xl border border-line bg-ink-2 p-8">
      <h1 className="font-display text-5xl font-extrabold leading-none tracking-tight">
        {isLogin ? "Welcome back." : "Join the radar."}
      </h1>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Email
        <input name="email" type="email" autoComplete="email" required className={field} placeholder="you@example.com" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Password
        <input name="password" type="password" required minLength={isLogin ? undefined : 8}
          autoComplete={isLogin ? "current-password" : "new-password"} className={field} placeholder={isLogin ? "" : "At least 8 characters"} />
      </label>
      <div aria-live="polite" className="min-h-6 text-sm">
        {state.error && <p className="font-semibold text-hotpink">{state.error}</p>}
        {state.message && <p className="font-semibold text-volt">{state.message}</p>}
      </div>
      <button disabled={pending} className="rounded-full bg-volt px-6 py-3 font-extrabold text-ink disabled:opacity-60">
        {pending ? "One sec…" : isLogin ? "Log in" : "Create account"}
      </button>
      <p className="text-sm text-mist">
        {isLogin ? "New here? " : "Already have an account? "}
        <Link href={isLogin ? "/signup" : "/login"} className="font-bold text-volt underline">
          {isLogin ? "Sign up" : "Log in"}
        </Link>
      </p>
    </form>
  );
}

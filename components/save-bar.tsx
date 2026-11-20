"use client";

import { Check } from "lucide-react";
import { useEffect, useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Sticky "unsaved changes" bar shared by the artist and city editors. Nothing is written until Save is pressed. */
export function SaveBar({ changes, saving, onSave, onDiscard, label, savedNote, error }: {
  changes: number; saving: boolean; onSave: () => void; onDiscard: () => void; label: string; savedNote?: string; error?: string;
}) {
  return (
    <div aria-live="polite" className="flex flex-col gap-2">
      {changes > 0 && <Bar changes={changes} saving={saving} onSave={onSave} onDiscard={onDiscard} label={label} />}
      {changes === 0 && savedNote && (
        <p className="flex items-center gap-2 text-sm font-semibold text-volt"><Check aria-hidden className="size-4" />{savedNote}</p>
      )}
      {error && <p className="text-sm font-semibold text-hotpink">{error}</p>}
    </div>
  );
}

function Bar({ changes, saving, onSave, onDiscard, label }: { changes: number; saving: boolean; onSave: () => void; onDiscard: () => void; label: string }) {
  const bar = useRef<HTMLDivElement>(null);
  const count = useRef<HTMLSpanElement>(null);
  useGSAP(() => {            // slides up when the first change is staged
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => { gsap.from(bar.current, { y: 70, autoAlpha: 0, scale: 0.96, duration: 0.55, ease: "back.out(1.7)" }); });
    return () => mm.revert();
  }, { scope: bar });
  useGSAP(() => {            // the counter bumps on every further change
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => { gsap.fromTo(count.current, { scale: 1.35 }, { scale: 1, duration: 0.35, ease: "back.out(3)" }); });
    return () => mm.revert();
  }, { dependencies: [changes], scope: bar });
  return (
    <div ref={bar} className="sticky bottom-3 z-20 flex flex-wrap items-center gap-3 rounded-2xl border-2 border-acid bg-ink-2/95 p-3 shadow-xl backdrop-blur">
      <span className="font-bold text-acid"><span ref={count} className="inline-block">{changes}</span> unsaved change{changes === 1 ? "" : "s"}</span>
      <button type="button" disabled={saving} onClick={onSave}
        className="rounded-full bg-volt px-6 py-2 font-extrabold text-ink disabled:opacity-60">{saving ? "Saving…" : label}</button>
      <button type="button" disabled={saving} onClick={onDiscard} className="rounded-full border border-line px-4 py-2 text-sm font-semibold">Discard</button>
    </div>
  );
}

/** Warn before leaving the page with unsaved edits. */
export function useUnsavedWarning(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
}

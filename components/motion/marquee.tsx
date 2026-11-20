"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Decorative scrolling ticker. Hidden from assistive tech; static when motion is reduced. */
export function Marquee({ items, className }: { items: string[]; className?: string }) {
  const track = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const el = track.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      const tween = gsap.to(el, { xPercent: -50, ease: "none", duration: 55, repeat: -1 });
      const slow = () => gsap.to(tween, { timeScale: 0.25, duration: 0.6 });
      const fast = () => gsap.to(tween, { timeScale: 1, duration: 0.6 });
      el.parentElement?.addEventListener("pointerenter", slow);
      el.parentElement?.addEventListener("pointerleave", fast);
    });
    return () => mm.revert();
  }, { scope: track });
  const row = items.map((n) => (
    <span key={n} className="flex items-center gap-6 whitespace-nowrap">
      <span>{n}</span><span className="text-volt">✦</span>
    </span>
  ));
  return (
    <div aria-hidden="true" className={`overflow-hidden ${className ?? ""}`}>
      <div ref={track} className="flex w-max gap-6">{row}{row}</div>
    </div>
  );
}

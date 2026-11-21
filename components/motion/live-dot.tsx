"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Small pulsing dot to mark "live"/"new". Decorative. */
export function LiveDot({ className = "bg-volt" }: { className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      const t = gsap.fromTo(el.querySelector("[data-ring]"), { scale: 1, autoAlpha: 0.7 }, { scale: 2.6, autoAlpha: 0, duration: 1.4, repeat: -1, ease: "power2.out" });
      return () => { t.kill(); };
    });
    return () => mm.revert();
  }, { scope: ref });
  return (
    <span aria-hidden ref={ref} className="relative inline-flex size-2.5">
      <span data-ring className={`absolute inset-0 rounded-full ${className} opacity-0`} />
      <span className={`relative size-2.5 rounded-full ${className}`} />
    </span>
  );
}

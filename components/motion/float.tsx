"use client";

import type { ReactNode } from "react";
import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Slow, gentle drift for decorative elements, with a slide-in entrance. */
export function Float({ children, className, amount = 10, delay = 0 }: { children: ReactNode; className?: string; amount?: number; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      gsap.from(el, { autoAlpha: 0, x: 60, rotation: 6, duration: 1, delay: 0.5 + delay, ease: "power4.out" });
      gsap.to(el, { y: -amount, duration: 3 + delay, yoyo: true, repeat: -1, ease: "sine.inOut", delay: 1.4 + delay });
    });
    return () => mm.revert();
  }, { scope: ref });
  return <div ref={ref} className={className}>{children}</div>;
}

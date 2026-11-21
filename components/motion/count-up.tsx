"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Number that counts up when it scrolls into view. The real value is always in the DOM text (and read by assistive tech). */
export function CountUp({ value, className }: { value: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      const state = { n: 0 };
      el.setAttribute("aria-label", String(value));
      const t = gsap.to(state, {
        n: value, duration: 1.4, ease: "power3.out", snap: { n: 1 },
        scrollTrigger: { trigger: el, start: "top 95%", once: true },
        onUpdate: () => { el.textContent = String(state.n); },
        onComplete: () => { el.textContent = String(value); },
      });
      return () => { t.scrollTrigger?.kill(); t.kill(); el.textContent = String(value); };
    });
    return () => mm.revert();
  }, { scope: ref, dependencies: [value] });
  return <span ref={ref} className={className}>{value}</span>;
}

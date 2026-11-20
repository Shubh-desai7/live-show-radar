"use client";

import type { ReactNode } from "react";
import { useRef } from "react";
import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from "@/lib/motion/gsap";

/** A content panel that slides in when it mounts (or when scrolled into view, if it starts below the fold). */
export function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      gsap.set(el, { autoAlpha: 0, y: 34 });
      const show = () => gsap.to(el, { autoAlpha: 1, y: 0, duration: 0.8, ease: "power3.out", clearProps: "transform" });
      if (el.getBoundingClientRect().top > window.innerHeight * 0.92) ScrollTrigger.create({ trigger: el, start: "top 92%", once: true, onEnter: show });
      else show();
    });
    return () => mm.revert();
  }, { scope: ref });
  return (
    <section ref={ref} data-section className="flex flex-col gap-4 rounded-3xl border border-line bg-ink-2 p-6">
      <div>
        <h2 className="font-display text-2xl font-extrabold">{title}</h2>
        {hint && <p className="text-mist">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

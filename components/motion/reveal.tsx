"use client";

import type { ElementType, ReactNode } from "react";
import { useRef } from "react";
import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from "@/lib/motion/gsap";

/** Staggers its direct children in. Children are pre-hidden by CSS (see globals.css) until GSAP takes over, so there is no flash. */
export function Reveal({ children, className, as: Tag = "div", stagger = 0.08, y = 26, delay = 0, scroll = false }: {
  children: ReactNode; className?: string; as?: ElementType; stagger?: number; y?: number; delay?: number; scroll?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      const items = Array.from(el.children) as HTMLElement[];
      if (!items.length) return;
      gsap.set(items, { autoAlpha: 0, y });
      const show = (targets: Element[]) => gsap.to(targets, { autoAlpha: 1, y: 0, duration: 0.75, stagger, delay, ease: "power3.out", clearProps: "transform" });
      if (scroll) ScrollTrigger.batch(items, { start: "top 90%", once: true, onEnter: (batch) => { show(batch); } });
      else show(items);
    });
    return () => mm.revert();
  }, { scope: ref });
  return <Tag ref={ref} data-reveal-group className={className}>{children}</Tag>;
}

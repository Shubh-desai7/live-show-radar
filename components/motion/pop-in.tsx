"use client";

import type { ElementType, ReactNode } from "react";
import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Chip/list item that pops in when it appears (e.g. a newly staged artist). */
export function PopIn({ children, className, as: Tag = "div" }: { children: ReactNode; className?: string; as?: ElementType }) {
  const ref = useRef<HTMLElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => { gsap.from(el, { scale: 0.6, autoAlpha: 0, duration: 0.45, ease: "back.out(2.2)" }); });
    return () => mm.revert();
  }, { scope: ref });
  return <Tag ref={ref} className={className}>{children}</Tag>;
}

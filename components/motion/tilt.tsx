"use client";

import type { ReactNode } from "react";
import { useRef } from "react";
import { FINE_POINTER, gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Subtle 3D tilt that follows the pointer. Mouse/trackpad only; off for touch and reduced motion. */
export function Tilt({ children, className, max = 6 }: { children: ReactNode; className?: string; max?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(`${MOTION_OK} and ${FINE_POINTER}`, () => {
      gsap.set(el, { transformPerspective: 900 });
      const rx = gsap.quickTo(el, "rotationX", { duration: 0.45, ease: "power3.out" });
      const ry = gsap.quickTo(el, "rotationY", { duration: 0.45, ease: "power3.out" });
      const lift = gsap.quickTo(el, "y", { duration: 0.35, ease: "power3.out" });
      const move = (e: PointerEvent) => {
        const r = el.getBoundingClientRect();
        ry(((e.clientX - r.left) / r.width - 0.5) * max * 2);
        rx(-((e.clientY - r.top) / r.height - 0.5) * max * 2);
        lift(-6);
      };
      const leave = () => { rx(0); ry(0); lift(0); };
      el.addEventListener("pointermove", move);
      el.addEventListener("pointerleave", leave);
      return () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerleave", leave); };
    });
    return () => mm.revert();
  }, { scope: ref });
  return <div ref={ref} className={className}>{children}</div>;
}

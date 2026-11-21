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
      const glow = document.createElement("div");           // pointer-following highlight (decorative, pointer-events none)
      glow.setAttribute("aria-hidden", "true");
      Object.assign(glow.style, { position: "absolute", inset: "0", borderRadius: "inherit", pointerEvents: "none", opacity: "0",
        background: "radial-gradient(260px circle at var(--gx,50%) var(--gy,50%), rgba(255,255,255,.18), transparent 60%)", mixBlendMode: "overlay" });
      if (getComputedStyle(el).position === "static") el.style.position = "relative";
      el.appendChild(glow);
      const glowTo = gsap.quickTo(glow, "opacity", { duration: 0.3 });
      const track = (e: PointerEvent) => {
        const r = el.getBoundingClientRect();
        glow.style.setProperty("--gx", `${e.clientX - r.left}px`);
        glow.style.setProperty("--gy", `${e.clientY - r.top}px`);
        glowTo(1);
      };
      el.addEventListener("pointermove", track);
      const leave = () => { rx(0); ry(0); lift(0); glowTo(0); };
      el.addEventListener("pointermove", move);
      el.addEventListener("pointerleave", leave);
      return () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointermove", track); el.removeEventListener("pointerleave", leave); glow.remove(); };
    });
    return () => mm.revert();
  }, { scope: ref });
  return <div ref={ref} className={className}>{children}</div>;
}

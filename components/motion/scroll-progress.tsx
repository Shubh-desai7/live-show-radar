"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Thin gradient bar at the top that fills as the page scrolls. Decorative; off under reduced motion. */
export function ScrollProgress() {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      gsap.set(el, { scaleX: 0, transformOrigin: "0 50%" });
      const t = gsap.to(el, { scaleX: 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: 0.3 } });
      return () => { t.scrollTrigger?.kill(); t.kill(); };
    });
    return () => mm.revert();
  }, { scope: ref });
  return <div aria-hidden ref={ref} className="pointer-events-none fixed inset-x-0 top-0 z-50 h-1 origin-left scale-x-0 bg-gradient-to-r from-volt via-hotpink to-grape" />;
}

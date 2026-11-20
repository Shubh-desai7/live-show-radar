"use client";

import { useEffect, useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Re-mounts on every navigation: a quick fade/rise between pages. Also hands over from the CSS pre-hide to GSAP. */
export default function Template({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      gsap.fromTo(el, { autoAlpha: 0, y: 10 }, { autoAlpha: 1, y: 0, duration: 0.4, ease: "power2.out", clearProps: "transform" });
    });
    return () => mm.revert();
  }, { scope: ref });

  useEffect(() => {
    // Safety net: once the page has loaded, stop pre-hiding anything GSAP has not claimed, so content can never stay invisible.
    const release = () => window.setTimeout(() => document.documentElement.removeAttribute("data-motion"), 2200);
    if (document.readyState === "complete") release();
    else window.addEventListener("load", release, { once: true });
  }, []);

  return <div ref={ref}>{children}</div>;
}

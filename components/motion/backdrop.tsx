"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

/** Two blurred colour blobs drifting slowly behind the page. Purely decorative; static under reduced motion. */
export function Backdrop() {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      gsap.to("[data-blob='a']", { x: 90, y: 60, scale: 1.15, duration: 14, yoyo: true, repeat: -1, ease: "sine.inOut" });
      gsap.to("[data-blob='b']", { x: -80, y: -70, scale: 0.9, duration: 17, yoyo: true, repeat: -1, ease: "sine.inOut" });
    });
    return () => mm.revert();
  }, { scope: ref });
  return (
    <div ref={ref} aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div data-blob="a" className="absolute -left-40 top-10 size-[34rem] rounded-full bg-grape/25 blur-[120px]" />
      <div data-blob="b" className="absolute -right-32 top-1/3 size-[30rem] rounded-full bg-volt/15 blur-[120px]" />
    </div>
  );
}

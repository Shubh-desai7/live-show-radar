"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/motion/gsap";

const WORDS: { text: string; className?: string }[] = [
  { text: "Zero" }, { text: "missed", className: "text-volt" }, { text: "shows." },
];

/** Big headline that rises in word by word. The h1 keeps a plain-text label for screen readers. */
export function HeroTitle({ className }: { className?: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useGSAP(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    mm.add(MOTION_OK, () => {
      const words = el.querySelectorAll("[data-word]");
      gsap.fromTo(words, { yPercent: 115, rotation: 7, autoAlpha: 0 },
        { yPercent: 0, rotation: 0, autoAlpha: 1, duration: 1, stagger: 0.12, ease: "power4.out", delay: 0.1 });
      gsap.to(el.querySelector("[data-volt]"), { rotation: -2, duration: 2.6, yoyo: true, repeat: -1, ease: "sine.inOut", delay: 1.2 });
    });
    return () => mm.revert();
  }, { scope: ref });
  return (
    <h1 ref={ref} aria-label="Zero missed shows." className={className}>
      {WORDS.map((w) => (
        <span key={w.text} aria-hidden="true" className="mr-[0.22em] inline-block overflow-hidden pb-[0.08em] align-bottom last:mr-0">
          <span data-word {...(w.className ? { "data-volt": true } : {})} className={`inline-block origin-bottom-left ${w.className ?? ""}`}>{w.text}</span>
        </span>
      ))}
    </h1>
  );
}

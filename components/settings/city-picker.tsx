"use client";

import { Check } from "lucide-react";
import { useState, useTransition } from "react";
import { INDIAN_CITIES } from "@/lib/cities";
import { toggleCity } from "@/lib/settings/actions";
import { cn } from "@/lib/utils/cn";

export function CityPicker({ selected }: { selected: string[] }) {
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();
  const set = new Set(selected);
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-wrap gap-2">
        {INDIAN_CITIES.map((c) => {
          const on = set.has(c);
          return (
            <li key={c}>
              <button type="button" aria-pressed={on} disabled={pending}
                onClick={() => start(async () => { const r = await toggleCity(c, !on); setError(r.error); })}
                className={cn("flex items-center gap-1 rounded-full border-2 px-4 py-2 font-bold transition-colors",
                  on ? "border-volt bg-volt text-ink" : "border-line text-bone hover:border-mist")}>
                {on && <Check aria-hidden className="size-4" />}{c}
              </button>
            </li>
          );
        })}
      </ul>
      <p aria-live="polite" className="min-h-5 text-sm font-semibold text-hotpink">{error}</p>
    </div>
  );
}

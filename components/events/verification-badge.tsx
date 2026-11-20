import { BadgeCheck, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { confidenceLabel, type Confidence } from "@/lib/events/status";

/** Sticker-style status badge. Rumoured events have no badge: they are never shown. */
export function VerificationBadge({ confidence }: { confidence: Exclude<Confidence, "rumoured"> }) {
  const confirmed = confidence === "confirmed";
  const Icon = confirmed ? BadgeCheck : HelpCircle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide",
        confirmed ? "bg-volt text-ink" : "border-2 border-dashed border-acid text-acid",
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      {confidenceLabel[confidence]}
    </span>
  );
}

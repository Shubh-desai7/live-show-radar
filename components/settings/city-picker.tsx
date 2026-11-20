"use client";

import { Check } from "lucide-react";
import { useState, useTransition } from "react";
import { SaveBar, useUnsavedWarning } from "@/components/save-bar";
import { diffSets } from "@/lib/artists/selection";
import { INDIAN_CITIES } from "@/lib/cities";
import { saveCities } from "@/lib/settings/actions";
import { cn } from "@/lib/utils/cn";

/** Pick cities locally; nothing is written until "Save cities" is pressed. */
export function CityPicker({ selected }: { selected: string[] }) {
  const [saved, setSaved] = useState(() => new Set(selected));
  const [draft, setDraft] = useState(() => new Set(selected));
  const [error, setError] = useState<string>();
  const [note, setNote] = useState<string>();
  const [saving, start] = useTransition();
  const { add, remove } = diffSets(saved, draft);
  const changes = add.length + remove.length;
  useUnsavedWarning(changes > 0);

  function toggle(c: string) {
    setNote(undefined);
    setDraft((s) => { const n = new Set(s); if (n.has(c)) n.delete(c); else n.add(c); return n; });
  }
  function save() {
    setError(undefined);
    start(async () => {
      const r = await saveCities([...draft]);
      if (r.error) { setError(r.error); return; }
      setSaved(new Set(draft));
      setNote("Saved. Alerts will only cover these cities.");
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-wrap gap-2">
        {INDIAN_CITIES.map((c) => {
          const on = draft.has(c);
          const unsaved = on !== saved.has(c);
          return (
            <li key={c}>
              <button type="button" aria-pressed={on} onClick={() => toggle(c)}
                className={cn("flex items-center gap-1 rounded-full border-2 px-4 py-2 font-bold transition-colors",
                  on ? (unsaved ? "border-dashed border-acid bg-acid/15 text-acid" : "border-volt bg-volt text-ink") : unsaved ? "border-dashed border-hotpink text-mist line-through" : "border-line text-bone hover:border-mist")}>
                {on && <Check aria-hidden className="size-4" />}{c}
              </button>
            </li>
          );
        })}
      </ul>
      <SaveBar changes={changes} saving={saving} onSave={save} onDiscard={() => { setDraft(new Set(saved)); setError(undefined); }}
        label="Save cities" savedNote={note} error={error} />
    </div>
  );
}

"use client";

import { Check, Send } from "lucide-react";
import { useState, useTransition } from "react";
import { createTelegramLink, disconnectTelegram, refreshTelegramStatus } from "@/lib/notifications/actions";

type Props = { configured: boolean; connected: boolean };

export function TelegramConnect({ configured, connected }: Props) {
  const [link, setLink] = useState<string>();
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();

  if (!configured) {
    return <p className="text-mist">Telegram alerts aren&apos;t set up on this server yet (placeholder: needs a bot token and username).</p>;
  }
  if (connected) {
    return (
      <div className="flex flex-wrap items-center gap-4">
        <span className="flex items-center gap-2 font-bold text-volt"><Check aria-hidden className="size-5" />Telegram connected</span>
        <button type="button" disabled={pending} className="rounded-full border border-line px-4 py-2 text-sm font-semibold"
          onClick={() => start(async () => { const r = await disconnectTelegram(); setError(r.error); setLink(undefined); })}>
          Disconnect
        </button>
        <p aria-live="polite" className="w-full text-sm font-semibold text-hotpink">{error}</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <button type="button" disabled={pending}
        className="flex w-fit items-center gap-2 rounded-full bg-volt px-6 py-3 font-extrabold text-ink disabled:opacity-60"
        onClick={() => start(async () => {
          const r = await createTelegramLink();
          setError(r.error); setLink(r.url);
          if (r.url) window.open(r.url, "_blank", "noopener,noreferrer");
        })}>
        <Send aria-hidden className="size-4" />Connect Telegram
      </button>
      {link && (
        <div className="flex flex-col gap-2 text-sm text-mist">
          <p>Telegram should open. Press <b>Start</b> in the chat. The link works once and expires in 15 minutes.</p>
          <a href={link} target="_blank" rel="noopener noreferrer" className="w-fit font-bold text-volt underline">Open Telegram again</a>
          <button type="button" disabled={pending} onClick={() => start(async () => { await refreshTelegramStatus(); })}
            className="w-fit rounded-full border border-line px-4 py-2 font-semibold text-bone">I pressed Start</button>
        </div>
      )}
      <p aria-live="polite" className="text-sm font-semibold text-hotpink">{error}</p>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ja } from "@/lib/i18n";
import type { EventConfirmation } from "@/lib/types";

interface Props {
  eventId: string;
  confirmation?: EventConfirmation | null;
}

// Shows an existing commercial-image confirmation link and a small form to
// add/update one. Posting persists to data/confirmations.json via the API
// route and refreshes the server-rendered data.
export default function ConfirmationControl({ eventId, confirmation }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(false);
    try {
      const res = await fetch("/api/confirmations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId, url, note }),
      });
      if (!res.ok) throw new Error(String(res.status));
      setOpen(false);
      setUrl("");
      setNote("");
      router.refresh();
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="confirm">
      {confirmation && (
        <div className="confirm__existing">
          <span className="confirm__badge">{ja.confirmationAdded}</span>{" "}
          <a href={confirmation.url} target="_blank" rel="noopener noreferrer">
            {ja.confirmationOpen} ↗
          </a>
          {confirmation.note && (
            <span className="muted"> — {confirmation.note}</span>
          )}
        </div>
      )}

      {open ? (
        <form className="confirm__form" onSubmit={save}>
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={ja.confirmationUrlPlaceholder}
            aria-label={ja.confirmationUrlPlaceholder}
          />
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={ja.confirmationNotePlaceholder}
            aria-label={ja.confirmationNotePlaceholder}
          />
          <button className="btn" type="submit" disabled={saving}>
            {saving ? ja.confirmationSaving : ja.confirmationSave}
          </button>
          {error && <span className="confirm__error">{ja.confirmationError}</span>}
        </form>
      ) : (
        <button
          className="btn btn--small"
          onClick={() => setOpen(true)}
          type="button"
        >
          + {ja.confirmationHeading}
        </button>
      )}
    </div>
  );
}

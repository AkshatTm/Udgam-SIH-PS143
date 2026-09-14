"use client";

import type { ReactNode } from "react";

// An external link that becomes a real <a href> ONLY for http(s). Anything else — an
// unparseable string, a `javascript:` / `data:` scheme, a scaffold's "TODO — real URL"
// placeholder — renders as plain text plus a note. A malformed source_url is a contract issue
// to surface, never something to trust into an href. Valid URLs are never filtered by host.

export default function ExternalLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  let safe: string | null = null;
  try {
    const u = new URL(href);
    if (u.protocol === "http:" || u.protocol === "https:") safe = u.href;
  } catch {
    /* not a parseable URL */
  }

  if (!safe) {
    return (
      <span className="text-ink-2">
        {href}
        <span className="ml-1.5 text-[12px] text-ink-3">
          (source link unavailable — malformed URL)
        </span>
      </span>
    );
  }

  return (
    <a
      href={safe}
      target="_blank"
      rel="noopener noreferrer"
      className="text-contact underline decoration-contact/35 underline-offset-2 transition-colors hover:decoration-contact"
    >
      {children}
      <span aria-hidden className="ml-1">
        ↗
      </span>
    </a>
  );
}

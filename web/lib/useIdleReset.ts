"use client";

// docs/04 C8 / Master §2.1: after ~90 s with no interaction, return to the Gallery in a clean
// state so the next judge never inherits the previous one's slider / selection / stage /
// layers / playback. No visible countdown, no "you are idle" UI — the docs ask for neither.
//
// This hook owns the timing, the listeners, and the navigation. The store owns what "clean"
// means (`resetToGallery`). Mounted once from CaseWorkspace, so it is active exactly while the
// workspace exists — the Gallery has no idle timer.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "./store";

export const IDLE_MS = 90_000;

// Genuine human input only. requestAnimationFrame, the autoplay loop, and bundle fetches emit
// none of these, so the app working on its own never keeps the session alive. pointerdown +
// pointermove cover mouse / touch / pen on every evergreen browser — no separate
// mousedown/touchstart. keydown covers the keyboard (incl. slider arrow keys); wheel covers
// scroll-wheel map zoom and panel scroll.
const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel"] as const;

export function useIdleReset(): void {
  const router = useRouter();

  useEffect(() => {
    let last = Date.now();
    let timer = 0;
    let fired = false;

    // Cheap: a bare timestamp write, safe to call on every pointermove. Never touches `timer`.
    const bump = () => {
      last = Date.now();
    };

    // Self-rescheduling: on expiry, either fire (once) or re-arm for exactly the time left.
    const check = () => {
      const idleFor = Date.now() - last;
      if (idleFor >= IDLE_MS) {
        if (fired) return;
        fired = true;
        useAppStore.getState().resetToGallery();
        router.push("/");
        return;
      }
      timer = window.setTimeout(check, IDLE_MS - idleFor);
    };

    const listenerOpts: AddEventListenerOptions = { capture: true, passive: true };
    for (const evt of ACTIVITY_EVENTS) {
      window.addEventListener(evt, bump, listenerOpts);
    }
    timer = window.setTimeout(check, IDLE_MS);

    return () => {
      window.clearTimeout(timer);
      for (const evt of ACTIVITY_EVENTS) {
        window.removeEventListener(evt, bump, listenerOpts);
      }
    };
  }, [router]);
}

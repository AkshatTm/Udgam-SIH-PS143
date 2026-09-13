# Demo machine runbook — 15 Sept, 17:00

For whoever drives the laptop. Production build only, never `npm run dev` in front of judges.

## 1. Bring the machine up to date (repo root)
```bash
git pull origin main
python scripts/validate_case.py cases/          # must print PASS on index + all 9
python scripts/sync_web_cases.py --clean        # copies bundles into web/public/cases
cd web
npm ci
npm run build
npm run start                                   # http://localhost:3000
```
Re-run the whole block after **every** pull, then redo the click path (§3). A bundle that
changed in `cases/` but was not synced shows stale data, not an error.

## 2. Machine settings (before the room)
- Plugged in; display sleep and screen saver **off**; power mode "best performance".
- Windows notifications / Focus: **do not disturb**. Pause Windows Update for the day.
- Close everything except one browser window (Chrome), one tab, full-screen (F11), zoom 100%.
- The app has no runtime network dependency (local fonts, no basemap tiles, static JSON), so it
  runs with wifi **off**. Test it that way; keep a phone hotspot as a spare, not a requirement.
- Charger, HDMI adapter, hotspot in the bag.

## 3. Click path (rehearse with wifi off, all 9 cases)
Gallery → case → Detect → Trace (let the auto-play finish, it rests rewound) → Attribute →
Verify (where available) → **Start over**. Watch for: any red contract-error card, a map that
isn't framing scene + particles + origin, stutter while scrubbing the time slider.

## 4. Fallback video
Record one full click path **on this machine, from this build** (Win+G Game Bar, or OBS).
Save to the desktop and to a phone. If the build changes, re-record.

## 5. Break ladder (in order, do not improvise)
1. Toggle the misbehaving layer off (layer bar, bottom).
2. Switch to another case.
3. Play the fallback video.
4. Spare laptop.
5. Deck on phone.

Between judges: press **Start over** (top right).

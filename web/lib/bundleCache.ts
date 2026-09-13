// In-memory cache of PARSED bundles, keyed by "<kind>:<case id>". Switching back to a case a
// judge already opened must not re-download and re-parse megabytes of particles (the loaders
// fetch with `cache: "no-store"`). Parsed bundles are cached, not raw JSON, so memory holds the
// compact Float32Arrays rather than nested number arrays.
//
// Memory only (web/CLAUDE.md: never localStorage). A page reload empties it, so a fresh
// `sync_web_cases.py` is picked up by reloading. A rejected load is evicted so it can be retried.

const cache = new Map<string, Promise<unknown>>();

export function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  const hit = cache.get(key);
  if (hit) return hit as Promise<T>;
  const p = load();
  cache.set(key, p);
  p.catch(() => {
    if (cache.get(key) === p) cache.delete(key);
  });
  return p;
}

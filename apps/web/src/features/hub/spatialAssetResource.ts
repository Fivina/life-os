export interface SpatialAssetLease<T> {
  promise: Promise<T>;
  release: () => void;
}

type OwnedAsset<T> = { value: T; dispose: () => void };

type Entry<T> = {
  promise: Promise<T>;
  clients: number;
  expired: boolean;
  asset: OwnedAsset<T> | null;
  timer: ReturnType<typeof setTimeout> | null;
};

/**
 * One resource per asset/loader identity; keep it at module scope to share loads.
 * Each acquire owns a lease, including while loading. Release exactly when that
 * client stops using the asset; release is idempotent and ends its right to use
 * even a subsequently resolved value. The loader transfers exclusive disposal
 * responsibility here and must provide a synchronous, non-throwing disposer.
 *
 * The default 30-second grace avoids fetch/parse churn on StrictMode and quick
 * remounts at the cost of retaining unused assets briefly. Pending loads cannot
 * be cancelled: after expiry their eventual results are disposed immediately.
 */
export function createSpatialAssetResource<T>(
  loader: () => Promise<OwnedAsset<T>>,
  options: { graceMs?: number } = {},
): { acquire: () => SpatialAssetLease<T> } {
  const graceMs = options.graceMs ?? 30_000;
  if (!Number.isFinite(graceMs) || graceMs < 0 || graceMs > 2_147_483_647) {
    throw new RangeError("graceMs must be a finite timer duration between 0 and 2147483647");
  }

  let current: Entry<T> | null = null;

  function expire(entry: Entry<T>) {
    if (entry.expired) return;
    entry.expired = true;
    if (entry.timer !== null) clearTimeout(entry.timer);
    entry.timer = null;
    if (current === entry) current = null;
    const asset = entry.asset;
    entry.asset = null;
    asset?.dispose();
  }

  function start(): Entry<T> {
    const entry: Entry<T> = {
      promise: Promise.resolve().then(loader).then(
        asset => {
          if (entry.expired) asset.dispose();
          else entry.asset = asset;
          return asset.value;
        },
        error => {
          expire(entry);
          throw error;
        },
      ),
      clients: 0,
      expired: false,
      asset: null,
      timer: null,
    };
    // A released client may no longer observe a failed pending load.
    void entry.promise.catch(() => {});
    return entry;
  }

  return {
    acquire() {
      const entry = current ?? (current = start());
      if (entry.timer !== null) clearTimeout(entry.timer);
      entry.timer = null;
      entry.clients += 1;
      let released = false;

      return {
        promise: entry.promise,
        release() {
          if (released) return;
          released = true;
          entry.clients -= 1;
          if (entry.clients === 0 && !entry.expired) {
            entry.timer = setTimeout(() => expire(entry), graceMs);
          }
        },
      };
    },
  };
}

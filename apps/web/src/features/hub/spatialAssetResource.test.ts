// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createSpatialAssetResource } from "./spatialAssetResource";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("spatial asset ownership", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shares one pending load between overlapping clients and keeps active assets alive", async () => {
    const value = { scene: "shared" };
    const dispose = vi.fn();
    const pending = deferred<{ value: typeof value; dispose: () => void }>();
    const loader = vi.fn(() => pending.promise);
    const resource = createSpatialAssetResource(loader, { graceMs: 100 });
    const first = resource.acquire();
    const second = resource.acquire();
    expect(first.promise).toBe(second.promise);
    await Promise.resolve();
    expect(loader).toHaveBeenCalledTimes(1);
    pending.resolve({ value, dispose });
    expect(await first.promise).toBe(value);
    expect(await second.promise).toBe(value);
    first.release();
    first.release();
    vi.advanceTimersByTime(1_000);
    expect(dispose).not.toHaveBeenCalled();
    second.release();
    vi.advanceTimersByTime(99);
    expect(dispose).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(dispose).toHaveBeenCalledTimes(1);
    second.release();
    vi.advanceTimersByTime(1_000);
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("reuses a pending load across StrictMode release/reacquire", async () => {
    const dispose = vi.fn();
    const pending = deferred<{ value: string; dispose: () => void }>();
    const loader = vi.fn(() => pending.promise);
    const resource = createSpatialAssetResource(loader, { graceMs: 100 });
    const mount = resource.acquire();
    mount.release();
    const remount = resource.acquire();
    expect(remount.promise).toBe(mount.promise);
    pending.resolve({ value: "scene", dispose });
    expect(await remount.promise).toBe("scene");
    vi.advanceTimersByTime(100);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(dispose).not.toHaveBeenCalled();
    remount.release();
    vi.advanceTimersByTime(100);
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("reuses a settled asset within the default grace and restarts grace on last release", async () => {
    const dispose = vi.fn();
    const loader = vi.fn(async () => ({ value: {}, dispose }));
    const resource = createSpatialAssetResource(loader);
    const first = resource.acquire();
    const value = await first.promise;
    first.release();
    vi.advanceTimersByTime(29_999);
    const returned = resource.acquire();
    expect(await returned.promise).toBe(value);
    vi.advanceTimersByTime(30_000);
    expect(dispose).not.toHaveBeenCalled();
    returned.release();
    vi.advanceTimersByTime(29_999);
    expect(dispose).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("disposes an abandoned late result without disturbing a new active load", async () => {
    const oldDispose = vi.fn();
    const newDispose = vi.fn();
    const oldLoad = deferred<{ value: string; dispose: () => void }>();
    const newLoad = deferred<{ value: string; dispose: () => void }>();
    const loader = vi.fn().mockReturnValueOnce(oldLoad.promise).mockReturnValueOnce(newLoad.promise);
    const resource = createSpatialAssetResource<string>(loader, { graceMs: 100 });
    const abandoned = resource.acquire();
    await Promise.resolve();
    abandoned.release();
    vi.advanceTimersByTime(100);
    const active = resource.acquire();
    await Promise.resolve();
    expect(loader).toHaveBeenCalledTimes(2);
    oldLoad.resolve({ value: "old", dispose: oldDispose });
    await abandoned.promise;
    abandoned.release();
    expect(oldDispose).toHaveBeenCalledTimes(1);
    const overlapping = resource.acquire();
    expect(overlapping.promise).toBe(active.promise);
    newLoad.resolve({ value: "new", dispose: newDispose });
    expect(await active.promise).toBe("new");
    vi.advanceTimersByTime(100);
    expect(newDispose).not.toHaveBeenCalled();
    active.release();
    overlapping.release();
    vi.advanceTimersByTime(100);
    expect(oldDispose).toHaveBeenCalledTimes(1);
    expect(newDispose).toHaveBeenCalledTimes(1);
  });

  it("keeps the original release deadline when an abandoned load resolves during grace", async () => {
    const dispose = vi.fn();
    const pending = deferred<{ value: string; dispose: () => void }>();
    const resource = createSpatialAssetResource(() => pending.promise, { graceMs: 100 });
    const lease = resource.acquire();
    lease.release();
    vi.advanceTimersByTime(90);
    pending.resolve({ value: "scene", dispose });
    await lease.promise;
    expect(dispose).not.toHaveBeenCalled();
    vi.advanceTimersByTime(10);
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("reloads after a settled asset expires", async () => {
    const firstDispose = vi.fn();
    const secondDispose = vi.fn();
    const loader = vi.fn()
      .mockResolvedValueOnce({ value: "first", dispose: firstDispose })
      .mockResolvedValueOnce({ value: "second", dispose: secondDispose });
    const resource = createSpatialAssetResource<string>(loader, { graceMs: 0 });
    const first = resource.acquire();
    expect(await first.promise).toBe("first");
    first.release();
    vi.advanceTimersByTime(0);
    const second = resource.acquire();
    expect(await second.promise).toBe("second");
    first.release();
    expect(loader).toHaveBeenCalledTimes(2);
    expect(firstDispose).toHaveBeenCalledTimes(1);
    expect(secondDispose).not.toHaveBeenCalled();
    second.release();
    vi.advanceTimersByTime(0);
    expect(secondDispose).toHaveBeenCalledTimes(1);
  });

  it("lets concurrent clients observe failure and retry while old leases still exist", async () => {
    const failure = new Error("parse failed");
    const pending = deferred<{ value: string; dispose: () => void }>();
    const dispose = vi.fn();
    const loader = vi.fn().mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce({ value: "retry", dispose });
    const resource = createSpatialAssetResource<string>(loader, { graceMs: 100 });
    const first = resource.acquire();
    const second = resource.acquire();
    const firstFailure = expect(first.promise).rejects.toBe(failure);
    const secondFailure = expect(second.promise).rejects.toBe(failure);
    pending.reject(failure);
    await Promise.all([firstFailure, secondFailure]);
    const retry = resource.acquire();
    expect(await retry.promise).toBe("retry");
    first.release();
    second.release();
    vi.advanceTimersByTime(100);
    expect(loader).toHaveBeenCalledTimes(2);
    expect(dispose).not.toHaveBeenCalled();
    retry.release();
    vi.advanceTimersByTime(100);
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("isolates a late abandoned rejection from the replacement entry", async () => {
    const pending = deferred<{ value: string; dispose: () => void }>();
    const dispose = vi.fn();
    const loader = vi.fn().mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce({ value: "replacement", dispose });
    const resource = createSpatialAssetResource<string>(loader, { graceMs: 0 });
    const abandoned = resource.acquire();
    await Promise.resolve();
    abandoned.release();
    vi.advanceTimersByTime(0);
    const active = resource.acquire();
    expect(await active.promise).toBe("replacement");
    pending.reject(new Error("abandoned failure"));
    // Leave the abandoned promise unobserved; the resource handles its rejection.
    await Promise.resolve();
    await Promise.resolve();
    const next = resource.acquire();
    expect(next.promise).toBe(active.promise);
    active.release();
    next.release();
    vi.advanceTimersByTime(0);
    expect(loader).toHaveBeenCalledTimes(2);
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("turns synchronous loader throws into retryable promise failures", async () => {
    const failure = new Error("loader failed");
    const dispose = vi.fn();
    const loader = vi.fn(() => Promise.resolve({ value: "retry", dispose }))
      .mockImplementationOnce(() => { throw failure; });
    const resource = createSpatialAssetResource(loader, { graceMs: 0 });
    const failed = resource.acquire();
    await expect(failed.promise).rejects.toBe(failure);
    failed.release();
    const retry = resource.acquire();
    expect(await retry.promise).toBe("retry");
    retry.release();
    vi.advanceTimersByTime(0);
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it.each([-1, NaN, Infinity, 2_147_483_648])("rejects invalid grace duration %s", graceMs => {
    const loader = vi.fn();
    expect(() => createSpatialAssetResource(loader, { graceMs })).toThrow(RangeError);
    expect(loader).not.toHaveBeenCalled();
  });
});

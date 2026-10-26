import assert from "node:assert/strict";
import test from "node:test";
import { ScopedRequestCache } from "./scopedRequestCache.ts";

test("deduplicates pending reads and expires cached responses", async () => {
  let now = 0, calls = 0;
  const cache = new ScopedRequestCache<number>(15, 2, () => now);
  const load = async () => ++calls;
  const one = cache.get(1, load), two = cache.get(1, load);
  assert.equal(one, two); assert.equal(await one, 1);
  assert.equal(await cache.get(1, load), 1);
  now = 16; assert.equal(await cache.get(1, load), 2);
});
test("invalidating prevents an older request from repopulating the cache", async () => {
  const cache = new ScopedRequestCache<string>();
  let resolve!: (value: string) => void;
  const pending = cache.get(1, () => new Promise<string>(r => { resolve = r; }));
  await Promise.resolve(); cache.clear();
  assert.equal(await cache.get(1, async () => 'fresh'), 'fresh');
  resolve('old'); await pending;
  assert.equal(await cache.get(1, async () => 'wrong'), 'fresh');
});
test("failures retry and cache capacity is bounded", async () => {
  const cache = new ScopedRequestCache<number>(15000, 2);
  await assert.rejects(cache.get(1, async () => { throw new Error('fail'); }));
  assert.equal(await cache.get(1, async () => 1), 1);
  await cache.get(2, async () => 2); await cache.get(3, async () => 3);
  assert.equal(await cache.get(1, async () => 4), 4);
});

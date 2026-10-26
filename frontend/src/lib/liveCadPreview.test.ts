import assert from "node:assert/strict";
import test from "node:test";
import { LatestPreviewQueue, previewFingerprint, previewReadiness } from "./liveCadPreview.ts";
import type { DoorFormData } from "./types";

const tick = () => new Promise(resolve => setImmediate(resolve));
const data = { dw: 900, dh: 2100, product_name: "不锈钢镀铜门", ys: "铜色", mshd: "80", sel_kx: "右开", sel_nk: "内开", st_val: "连体锁" } as DoorFormData;

test("commercial notes do not trigger CAD; geometry changes do", () => {
  assert.equal(previewFingerprint(data), previewFingerprint({ ...data, dhdw: "客户", sm: "备注", sl: "3樘" }));
  assert.notEqual(previewFingerprint(data), previewFingerprint({ ...data, dw: 1000 }));
  assert.equal(previewReadiness(data), "");
  assert.equal(previewReadiness({ ...data, dw: 0 }), "请输入有效宽度和高度");
  assert.equal(previewReadiness({ ...data, sel_nk: "" }), "请选择内外开向");
});

test("only one request runs; intermediate pending inputs are replaced and stale responses ignored", async () => {
  const calls: string[] = [], shown: string[] = [], busy: boolean[] = [];
  const resolve = new Map<string, (value: string) => void>();
  const queue = new LatestPreviewQueue<string>(key => {
    calls.push(key);
    return new Promise(done => resolve.set(key, done));
  }, { success: svg => shown.push(svg), error: () => assert.fail(), busy: value => busy.push(value) });
  queue.setDesired('a'); queue.enqueue('a', 'a');
  queue.setDesired('b'); queue.enqueue('b', 'b');
  queue.setDesired('c'); queue.enqueue('c', 'c');
  assert.deepEqual(calls, ['a']);
  resolve.get('a')!('svg-a'); await tick();
  assert.deepEqual(calls, ['a', 'c']);
  assert.deepEqual(shown, []);
  resolve.get('c')!('svg-c'); await tick();
  assert.deepEqual(shown, ['svg-c']); assert.deepEqual(busy, [true, false]);
});

test("cache reuses previous snapshots and keeps no more than eight", async () => {
  const calls: number[] = [];
  const queue = new LatestPreviewQueue<number>(async value => { calls.push(value); return `svg-${value}`; },
    { success: () => {}, error: () => assert.fail(), busy: () => {} });
  for (let n = 0; n < 9; n++) { queue.setDesired(String(n)); queue.enqueue(String(n), n); await tick(); }
  queue.setDesired('8'); queue.enqueue('8', 8); await tick();
  assert.equal(calls.length, 9);
  queue.setDesired('0'); queue.enqueue('0', 0); await tick();
  assert.equal(calls.length, 10);
});

test("cancelled pending work does not run and disposed views do not publish", async () => {
  let finish!: (value: string) => void;
  let count = 0;
  const queue = new LatestPreviewQueue<string>(() => { count++; return new Promise(done => { finish = done; }); },
    { success: () => assert.fail(), error: () => assert.fail(), busy: () => {} });
  queue.setDesired('a'); queue.enqueue('a', 'a');
  queue.setDesired('b'); queue.enqueue('b', 'b'); queue.cancelPending();
  queue.dispose(); finish('old-svg'); await tick();
  queue.enqueue('c', 'c'); assert.equal(count, 1);
});

test("oversized SVGs are displayed without keeping an unbounded cache", async () => {
  let calls = 0;
  const large = 'x'.repeat(4_000_001);
  const queue = new LatestPreviewQueue<string>(async () => { calls++; return large; },
    { success: value => assert.equal(value.length, large.length), error: () => assert.fail(), busy: () => {} });
  queue.setDesired('large'); queue.enqueue('large', 'large'); await tick();
  queue.enqueue('large', 'large'); await tick();
  assert.equal(calls, 2);
});

test("failed preview preserves the last successful result and can retry", async () => {
  const shown: string[] = [], errors: unknown[] = [];
  let fail = false;
  const queue = new LatestPreviewQueue<string>(async value => { if (fail) throw Error('failed'); return value; },
    { success: value => shown.push(value), error: value => errors.push(value), busy: () => {} });
  queue.setDesired('a'); queue.enqueue('a', 'svg-a'); await tick();
  fail = true; queue.setDesired('b'); queue.enqueue('b', 'svg-b'); await tick();
  assert.deepEqual(shown, ['svg-a']); assert.equal(errors.length, 1);
  fail = false; queue.enqueue('b', 'svg-b'); await tick();
  assert.deepEqual(shown, ['svg-a', 'svg-b']);
});

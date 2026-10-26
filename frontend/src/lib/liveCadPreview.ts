import type { DoorFormData } from "./types";

export function previewFingerprint(data: DoorFormData): string {
  const params = { ...data } as Record<string, unknown>;
  for (const key of ["dhdw", "gdmc", "dhrq", "ddh", "order_title", "hhxd", "sm", "sl"]) delete params[key];
  return JSON.stringify(params);
}

export function previewReadiness(data: DoorFormData): string {
  if (![data.dw, data.dh].every(value => Number.isFinite(Number(value)) && Number(value) > 0)) return "请输入有效宽度和高度";
  if (!data.product_name?.trim()) return "请选择产品名称";
  if (!data.ys?.trim()) return "请选择颜色";
  if (["牌匾", "铝艺栅栏", "雨棚", "其他"].includes(data.product_name)) return "";
  if (!Number.isFinite(Number(data.mshd)) || !(Number(data.mshd) > 0)) return "请填写门扇厚度";
  if (!["左开", "右开", "左右开"].includes(data.sel_kx)) return "请选择左右开向";
  if (!["内开", "外开", "内外开"].includes(data.sel_nk)) return "请选择内外开向";
  if (!data.st_val?.trim()) return "请选择锁体类型";
  return "";
}

type Job<T> = { key: string; input: T };
type PreviewCallbacks = {
  success: (svg: string, key: string) => void; error: (error: unknown) => void; busy: (busy: boolean) => void;
};

export class LatestPreviewQueue<T> {
  private desired = "";
  private pending: Job<T> | null = null;
  private running = false;
  private disposed = false;
  private cache = new Map<string, string>();
  private cachedChars = 0;
  private generate: (input: T) => Promise<string>;
  private callbacks: PreviewCallbacks;

  constructor(generate: (input: T) => Promise<string>, callbacks: PreviewCallbacks) {
    this.generate = generate;
    this.callbacks = callbacks;
  }

  setDesired(key: string) { this.desired = key; }
  cancelPending() { this.pending = null; }
  dispose() { this.disposed = true; this.pending = null; this.cache.clear(); this.cachedChars = 0; }

  enqueue(key: string, input: T) {
    if (this.disposed) return;
    this.pending = { key, input };
    void this.drain();
  }

  private async drain() {
    if (this.running || this.disposed) return;
    this.running = true;
    this.callbacks.busy(true);
    try {
      while (this.pending && !this.disposed) {
        const job = this.pending;
        this.pending = null;
        try {
          const svg = this.cache.get(job.key) ?? await this.generate(job.input);
          if (this.disposed) return;
          this.cachedChars -= this.cache.get(job.key)?.length ?? 0;
          this.cache.delete(job.key);
          if (svg.length <= 4_000_000) {
            this.cache.set(job.key, svg);
            this.cachedChars += svg.length;
          }
          while (this.cache.size > 8 || this.cachedChars > 4_000_000) {
            const oldest = this.cache.keys().next().value!;
            this.cachedChars -= this.cache.get(oldest)!.length;
            this.cache.delete(oldest);
          }
          if (job.key === this.desired) this.callbacks.success(svg, job.key);
        } catch (error) {
          if (!this.disposed && job.key === this.desired) this.callbacks.error(error);
        }
      }
    } finally {
      this.running = false;
      if (!this.disposed) this.callbacks.busy(false);
    }
  }
}

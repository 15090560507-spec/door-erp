/** Short-lived, owner-scoped read cache. Never persisted or shared across users. */
export class ScopedRequestCache<T> {
  private entries = new Map<number, { value?: T; expires: number; request?: Promise<T> }>();
  private ttl: number;
  private limit: number;
  private now: () => number;
  constructor(ttl = 15000, limit = 20, now = Date.now) {
    this.ttl = ttl; this.limit = limit; this.now = now;
  }

  clear() { this.entries.clear(); }

  get(id: number, load: () => Promise<T>): Promise<T> {
    const known = this.entries.get(id);
    if (known?.value !== undefined && known.expires > this.now()) return Promise.resolve(known.value);
    if (known?.request) return known.request;
    const entry: { value?: T; expires: number; request?: Promise<T> } = { expires: 0 };
    const request = Promise.resolve().then(load).then(value => {
      if (this.entries.get(id) === entry) {
        entry.value = value; entry.expires = this.now() + this.ttl; entry.request = undefined;
      }
      return value;
    }, error => {
      if (this.entries.get(id) === entry) this.entries.delete(id);
      throw error;
    });
    entry.request = request;
    this.entries.delete(id);
    this.entries.set(id, entry);
    while (this.entries.size > this.limit) this.entries.delete(this.entries.keys().next().value!);
    return request;
  }
}

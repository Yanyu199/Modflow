export class ResultSliceCache {
  constructor(maxBytes = 128 * 1024 * 1024) {
    this.maxBytes = maxBytes;
    this.items = new Map();
    this.currentBytes = 0;
  }

  get(key) {
    if (!this.items.has(key)) return null;
    const value = this.items.get(key);
    this.items.delete(key);
    this.items.set(key, value);
    return value.data;
  }

  set(key, data) {
    const bytes = data && data.byteLength !== undefined ? data.byteLength : 0;
    if (this.items.has(key)) {
      const old = this.items.get(key);
      this.currentBytes -= old.bytes;
      this.items.delete(key);
    }
    while (this.currentBytes + bytes > this.maxBytes && this.items.size > 0) {
      const oldestKey = this.items.keys().next().value;
      const oldest = this.items.get(oldestKey);
      this.currentBytes -= oldest.bytes;
      this.items.delete(oldestKey);
    }
    this.items.set(key, { data, bytes });
    this.currentBytes += bytes;
    return data;
  }

  clear() {
    this.items.clear();
    this.currentBytes = 0;
  }

  stats() {
    return {
      items: this.items.size,
      bytes: this.currentBytes,
      maxBytes: this.maxBytes
    };
  }
}

export const resultSliceCache = new ResultSliceCache();

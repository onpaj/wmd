/** Minimal <img> / container doubles so photo rendering can be tested without a browser. */

class FakeClassList {
  private readonly names = new Set<string>();

  add(name: string): void {
    this.names.add(name);
  }

  remove(name: string): void {
    this.names.delete(name);
  }

  contains(name: string): boolean {
    return this.names.has(name);
  }
}

export class FakeImage {
  readonly classList = new FakeClassList();
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private readonly loads: FakeImage[];
  private currentSrc = '';

  constructor(loads: FakeImage[]) {
    this.loads = loads;
  }

  get src(): string {
    return this.currentSrc;
  }

  /** Assigning a src queues a load; nothing is visible until the load is flushed. */
  set src(value: string) {
    this.currentSrc = value;
    this.loads.push(this);
  }

  get isActive(): boolean {
    return this.classList.contains('photo-img--active');
  }
}

export class FakeElement {
  textContent = '';
}

export class FakeContainer {
  readonly pendingLoads: FakeImage[] = [];
  readonly imgA = new FakeImage(this.pendingLoads);
  readonly imgB = new FakeImage(this.pendingLoads);
  readonly dateEl = new FakeElement();

  querySelector(selector: string): FakeImage | FakeElement {
    if (selector === '#photo-date') return this.dateEl;
    return selector === '#photo-a' ? this.imgA : this.imgB;
  }

  /** Simulate the browser finishing every outstanding image download. */
  flushLoads(): void {
    const queued = [...this.pendingLoads];
    this.pendingLoads.length = 0;
    queued.forEach(img => img.onload?.());
  }

  get activeSrc(): string | null {
    if (this.imgA.isActive) return this.imgA.src;
    if (this.imgB.isActive) return this.imgB.src;
    return null;
  }
}

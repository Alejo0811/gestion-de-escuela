/* Keeps independent browser sessions current without replacing an open draft. */
class StateSync {
  constructor({load, apply, canApply, status, expired, interval = 5000}) {
    Object.assign(this, {load, apply, canApply, status, expired, interval});
    this.version = 0;
    this.running = false;
    this.stopped = true;
    this.snapshot = '';
    this.onResume = () => this.refresh();
    this.onOffline = () => this.status('offline');
  }

  accept(state) {
    this.version++;
    this.snapshot = JSON.stringify(state);
    this.status('current');
  }

  invalidate() {
    // A response started before a local save must never undo that save onscreen.
    this.version++;
  }

  start(state) {
    this.stopped = false;
    this.accept(state);
    window.addEventListener('focus', this.onResume);
    window.addEventListener('online', this.onResume);
    window.addEventListener('offline', this.onOffline);
    document.addEventListener('visibilitychange', this.onResume);
    this.schedule();
  }

  schedule() {
    if (this.stopped) return;
    clearTimeout(this.timer);
    this.timer = setTimeout(async () => {
      await this.refresh();
      this.schedule();
    }, this.interval);
  }

  async refresh() {
    if (this.stopped || this.running || document.hidden) return;
    if (!navigator.onLine) return this.status('offline');
    const version = this.version;
    this.running = true;
    try {
      const state = await this.load();
      if (this.stopped || version !== this.version) return;
      if (JSON.stringify(state) !== this.snapshot) {
        if (!this.canApply()) return this.status('pending');
        this.accept(state);
        this.apply(state);
      }
      this.status('current');
    } catch (error) {
      if (this.stopped || version !== this.version) return;
      if (error.status === 401) {
        this.status('expired');
        if (this.canApply()) this.expired();
      } else {
        this.status(navigator.onLine ? 'error' : 'offline');
      }
    } finally {
      this.running = false;
    }
  }

  stop() {
    this.stopped = true;
    this.invalidate();
    clearTimeout(this.timer);
    window.removeEventListener('focus', this.onResume);
    window.removeEventListener('online', this.onResume);
    window.removeEventListener('offline', this.onOffline);
    document.removeEventListener('visibilitychange', this.onResume);
  }
}
window.StateSync = StateSync;

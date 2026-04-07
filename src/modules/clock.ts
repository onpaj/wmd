export function startClock(container: HTMLElement): void {
  function tick(): void {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    container.textContent = `${hh}:${mm}`;
  }
  tick();
  setInterval(tick, 1000);
}

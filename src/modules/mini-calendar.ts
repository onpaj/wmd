import { CalendarEvent } from '../types';

const CZECH_WEEKDAYS = ['po', 'út', 'st', 'čt', 'pá', 'so', 'ne'];

// Returns Monday-first day-of-week index (0=Monday, 6=Sunday)
function mondayFirst(jsDay: number): number {
  return (jsDay + 6) % 7;
}

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export function render(events: CalendarEvent[], container: HTMLElement): void {
  container.innerHTML = '';

  const today = new Date();
  const todayKey = toDateKey(today);

  // Start from Monday of the current week
  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - mondayFirst(today.getDay()));
  weekStart.setHours(0, 0, 0, 0);

  // Build map: dateKey → list of {color, title}
  const eventMap = new Map<string, Array<{ color: string; title: string }>>();
  for (const ev of events) {
    const d = new Date(ev.start);
    const key = toDateKey(d);
    if (!eventMap.has(key)) eventMap.set(key, []);
    eventMap.get(key)!.push({ color: ev.color, title: ev.title });
  }

  // Header row
  const header = document.createElement('div');
  header.className = 'mini-cal-header';
  for (const wd of CZECH_WEEKDAYS) {
    const cell = document.createElement('div');
    cell.className = 'mini-cal-weekday';
    cell.textContent = wd;
    header.appendChild(cell);
  }
  container.appendChild(header);

  // Grid: 3 weeks = 21 days
  const grid = document.createElement('div');
  grid.className = 'mini-cal-grid';

  for (let i = 0; i < 21; i++) {
    const day = new Date(weekStart);
    day.setDate(weekStart.getDate() + i);
    const dayKey = toDateKey(day);

    const cell = document.createElement('div');
    cell.className = 'mini-cal-cell';
    if (dayKey === todayKey) cell.classList.add('mini-cal-today');

    const num = document.createElement('span');
    num.className = 'mini-cal-day-num';
    num.textContent = String(day.getDate());
    cell.appendChild(num);

    const evList = eventMap.get(dayKey);
    if (evList && evList.length > 0) {
      const bars = document.createElement('div');
      bars.className = 'mini-cal-bars';
      for (const ev of evList.slice(0, 3)) {
        const bar = document.createElement('div');
        bar.className = 'mini-cal-bar';
        bar.style.background = ev.color;
        bar.textContent = ev.title;
        bars.appendChild(bar);
      }
      cell.appendChild(bars);
    }

    grid.appendChild(cell);
  }

  container.appendChild(grid);
}

import { CalendarEvent } from '../types';

const CZECH_DAYS = ['ne', 'po', 'út', 'st', 'čt', 'pá', 'so'];

function dateLabel(dateStr: string, todayStr: string): string {
  if (dateStr === todayStr) return 'dnes';
  const today = new Date(todayStr);
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  const tomorrowStr = tomorrow.toISOString().slice(0, 10);
  if (dateStr === tomorrowStr) return 'zítra';
  const d = new Date(dateStr);
  return CZECH_DAYS[d.getDay()];
}

function formatTime(isoStr: string): string {
  const d = new Date(isoStr);
  const h = d.getHours().toString().padStart(2, '0');
  const m = d.getMinutes().toString().padStart(2, '0');
  return `${h}:${m}`;
}

export function render(events: CalendarEvent[], container: HTMLElement): void {
  container.innerHTML = '';

  const todayStr = new Date().toISOString().slice(0, 10);

  // Group events by date
  const groups = new Map<string, CalendarEvent[]>();
  for (const ev of events) {
    const date = ev.start.slice(0, 10);
    if (!groups.has(date)) groups.set(date, []);
    groups.get(date)!.push(ev);
  }

  for (const [date, dayEvents] of groups) {
    const dayNum = date.slice(8, 10).replace(/^0/, '');
    const label = dateLabel(date, todayStr);

    const header = document.createElement('div');
    header.className = 'cal-date-header';
    header.textContent = `${dayNum} ${label}`;
    container.appendChild(header);

    for (const ev of dayEvents) {
      const row = document.createElement('div');
      row.className = 'cal-event';
      row.style.setProperty('--cal-color', ev.color);

      const time = document.createElement('span');
      time.className = 'cal-time';
      if (ev.all_day) {
        time.textContent = 'celý den';
      } else {
        time.textContent = `${formatTime(ev.start)} – ${formatTime(ev.end)}`;
      }

      const title = document.createElement('span');
      title.className = 'cal-title';
      title.textContent = ev.title;

      row.appendChild(time);
      row.appendChild(title);
      container.appendChild(row);
    }
  }
}

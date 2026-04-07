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
    const numSpan = document.createElement('span');
    numSpan.className = 'cal-day-num';
    numSpan.textContent = dayNum;
    const labelSpan = document.createElement('span');
    labelSpan.className = 'cal-day-label';
    labelSpan.textContent = label;
    header.appendChild(numSpan);
    header.appendChild(labelSpan);
    container.appendChild(header);

    for (const ev of dayEvents) {
      const row = document.createElement('div');
      row.className = 'cal-event';
      row.style.setProperty('--cal-color', ev.color);

      const timeCol = document.createElement('div');
      timeCol.className = 'cal-time-col';

      if (ev.all_day) {
        const start = document.createElement('span');
        start.className = 'cal-time-start';
        start.textContent = 'celý den';
        timeCol.appendChild(start);
      } else {
        const start = document.createElement('span');
        start.className = 'cal-time-start';
        start.textContent = formatTime(ev.start);
        const end = document.createElement('span');
        end.className = 'cal-time-end';
        end.textContent = formatTime(ev.end);
        timeCol.appendChild(start);
        timeCol.appendChild(end);
      }

      const title = document.createElement('span');
      title.className = 'cal-title';
      title.textContent = ev.title;

      row.appendChild(timeCol);
      row.appendChild(title);
      container.appendChild(row);
    }
  }
}

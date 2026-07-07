import { CalendarEvent } from '../types';

const CZECH_WEEKDAYS = ['po', 'út', 'st', 'čt', 'pá', 'so', 'ne'];

// Returns Monday-first day-of-week index (0=Monday, 6=Sunday)
function mondayFirst(jsDay: number): number {
  return (jsDay + 6) % 7;
}

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

// Longest span (in days) we will expand a single event across, guarding against
// malformed feeds with runaway or reversed date ranges.
const MAX_EVENT_SPAN_DAYS = 366;

// Returns the local date key for every day an event covers, so multi-day events
// (e.g. an "apartmán" booking) appear on each day, not only their start.
//
// iCal all-day events use an EXCLUSIVE end date — DTEND is the day *after* the
// last day — whereas timed events end at an inclusive moment in time.
export function eventDayKeys(ev: CalendarEvent): string[] {
  const start = new Date(ev.start);
  const startDay = new Date(start.getFullYear(), start.getMonth(), start.getDate());

  const end = new Date(ev.end);
  const lastDay = new Date(end.getFullYear(), end.getMonth(), end.getDate());
  if (ev.all_day) {
    lastDay.setDate(lastDay.getDate() - 1);
  }

  // Zero-length or reversed span (e.g. a single all-day event, or a missing
  // DTEND where end === start) collapses to just the start day.
  if (lastDay < startDay) {
    return [toDateKey(startDay)];
  }

  const keys: string[] = [];
  const cursor = new Date(startDay);
  for (let i = 0; i < MAX_EVENT_SPAN_DAYS && cursor <= lastDay; i++) {
    keys.push(toDateKey(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return keys;
}

export function render(events: CalendarEvent[], container: HTMLElement): void {
  container.innerHTML = '';

  const today = new Date();
  const todayKey = toDateKey(today);

  // Start from Monday of the current week
  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - mondayFirst(today.getDay()));
  weekStart.setHours(0, 0, 0, 0);

  // Build map: dateKey → list of {color, title}. Multi-day events are added to
  // every day they span so bookings show across their whole range.
  const eventMap = new Map<string, Array<{ color: string; title: string }>>();
  for (const ev of events) {
    for (const key of eventDayKeys(ev)) {
      if (!eventMap.has(key)) eventMap.set(key, []);
      eventMap.get(key)!.push({ color: ev.color, title: ev.title });
    }
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

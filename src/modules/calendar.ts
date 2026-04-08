import { CalendarEvent } from '../types';

const CZECH_DAYS = ['ne', 'po', 'út', 'st', 'čt', 'pá', 'so'];

type MergedEvent = CalendarEvent & { colors: string[] };

function mergeByTimeslot(events: CalendarEvent[]): MergedEvent[] {
  const merged = new Map<string, MergedEvent>();
  for (const ev of events) {
    const key = `${ev.title}|${ev.start}|${ev.end}|${ev.all_day}`;
    if (merged.has(key)) {
      const m = merged.get(key)!;
      if (!m.colors.includes(ev.color)) m.colors.push(ev.color);
    } else {
      merged.set(key, { ...ev, colors: [ev.color] });
    }
  }
  return Array.from(merged.values());
}

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

  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);

  // Filter out past events: skip events that ended before now
  const visibleEvents = events.filter(ev => {
    if (ev.all_day) return ev.start.slice(0, 10) >= todayStr;
    return new Date(ev.end) > now;
  });

  // Group events by date
  const groups = new Map<string, CalendarEvent[]>();
  for (const ev of visibleEvents) {
    const date = ev.start.slice(0, 10);
    if (!groups.has(date)) groups.set(date, []);
    groups.get(date)!.push(ev);
  }

  for (const [date, dayEvents] of groups) {
    const dayNum = date.slice(8, 10);
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

    for (const ev of mergeByTimeslot(dayEvents)) {
      const row = document.createElement('div');
      row.className = 'cal-event';

      if (ev.colors.length === 1) {
        row.style.setProperty('--cal-color', ev.colors[0]);
      } else {
        row.classList.add('cal-event--multi');
        const n = ev.colors.length;
        const borderStops = ev.colors.map((c, i) =>
          `${c} ${(i / n * 100).toFixed(1)}% ${((i + 1) / n * 100).toFixed(1)}%`
        ).join(', ');
        const bgStops = ev.colors.map((c, i) =>
          `color-mix(in srgb, ${c} 22%, transparent) ${(i / n * 100).toFixed(1)}% ${((i + 1) / n * 100).toFixed(1)}%`
        ).join(', ');
        row.style.backgroundImage = `linear-gradient(to bottom, ${borderStops}), linear-gradient(to right, ${bgStops})`;
        row.style.backgroundSize = '4px 100%, calc(100% - 4px) 100%';
        row.style.backgroundPosition = 'left center, right center';
        row.style.backgroundRepeat = 'no-repeat';
      }

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

      const titleWrapper = document.createElement('div');
      titleWrapper.className = 'cal-title-col';

      const title = document.createElement('span');
      title.className = 'cal-title';
      title.textContent = ev.title;
      titleWrapper.appendChild(title);

      if (ev.location) {
        const loc = document.createElement('span');
        loc.className = 'cal-location';
        loc.textContent = ev.location;
        titleWrapper.appendChild(loc);
      }

      row.appendChild(timeCol);
      row.appendChild(titleWrapper);
      container.appendChild(row);
    }
  }
}

import { CalendarEvent } from '../types';

const CZECH_WEEKDAYS = ['po', 'út', 'st', 'čt', 'pá', 'so', 'ne'];

// Returns Monday-first day-of-week index (0=Monday, 6=Sunday)
function mondayFirst(jsDay: number): number {
  return (jsDay + 6) % 7;
}

export function render(events: CalendarEvent[], container: HTMLElement): void {
  container.innerHTML = '';

  const today = new Date();
  const todayYear = today.getFullYear();
  const todayMonth = today.getMonth();
  const todayDate = today.getDate();

  const firstDay = new Date(todayYear, todayMonth, 1);
  const daysInMonth = new Date(todayYear, todayMonth + 1, 0).getDate();
  const startOffset = mondayFirst(firstDay.getDay());

  // Build map: day-of-month → unique colors with events
  const dotMap = new Map<number, Set<string>>();
  for (const ev of events) {
    const d = new Date(ev.start);
    if (d.getFullYear() === todayYear && d.getMonth() === todayMonth) {
      const day = d.getDate();
      if (!dotMap.has(day)) dotMap.set(day, new Set());
      dotMap.get(day)!.add(ev.color);
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

  // Grid
  const grid = document.createElement('div');
  grid.className = 'mini-cal-grid';

  // Empty cells before first day
  for (let i = 0; i < startOffset; i++) {
    const empty = document.createElement('div');
    empty.className = 'mini-cal-cell mini-cal-empty';
    grid.appendChild(empty);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const cell = document.createElement('div');
    cell.className = 'mini-cal-cell';
    if (day === todayDate) cell.classList.add('mini-cal-today');

    const num = document.createElement('span');
    num.className = 'mini-cal-day-num';
    num.textContent = String(day);
    cell.appendChild(num);

    const colors = dotMap.get(day);
    if (colors && colors.size > 0) {
      const dots = document.createElement('div');
      dots.className = 'mini-cal-dots';
      let count = 0;
      for (const color of colors) {
        if (count >= 3) break;
        const dot = document.createElement('span');
        dot.className = 'mini-cal-dot';
        dot.style.background = color;
        dots.appendChild(dot);
        count++;
      }
      cell.appendChild(dots);
    }

    grid.appendChild(cell);
  }

  container.appendChild(grid);
}

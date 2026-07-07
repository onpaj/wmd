import { CalendarEvent } from '../types';

const CZECH_WEEKDAYS = ['po', 'út', 'st', 'čt', 'pá', 'so', 'ne'];
const NUM_WEEKS = 3;
const DAYS_PER_WEEK = 7;
const MAX_LANES = 3; // max stacked event bars per week row
const MS_PER_DAY = 24 * 60 * 60 * 1000;

// Returns Monday-first day-of-week index (0=Monday, 6=Sunday)
function mondayFirst(jsDay: number): number {
  return (jsDay + 6) % 7;
}

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

// Local midnight for the given date, stripping the time component.
function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

// Whole-day difference (a - b) between two local-midnight dates.
function dayDiff(a: Date, b: Date): number {
  return Math.round((a.getTime() - b.getTime()) / MS_PER_DAY);
}

interface EventSpan {
  ev: CalendarEvent;
  startDay: Date; // first covered day (inclusive, local midnight)
  lastDay: Date; // last covered day (inclusive, local midnight)
}

// Resolves an event to its inclusive [startDay, lastDay] day range so a
// multi-day event can be drawn as one connected bar.
//
// iCal all-day events use an EXCLUSIVE end date — DTEND is the day *after* the
// last day — whereas timed events end at an inclusive moment in time.
export function eventSpan(ev: CalendarEvent): EventSpan {
  const startDay = startOfDay(new Date(ev.start));
  const lastDay = startOfDay(new Date(ev.end));
  if (ev.all_day) {
    lastDay.setDate(lastDay.getDate() - 1);
  }
  // Zero-length, reversed, or missing-DTEND spans (end === start) collapse to
  // just the start day.
  if (lastDay < startDay) {
    return { ev, startDay, lastDay: new Date(startDay) };
  }
  return { ev, startDay, lastDay };
}

// Greedily assigns each event to the first lane (stack row) whose last occupied
// column ends before the event starts, so bars never overlap within a week.
function assignLane(colStart: number, laneLastCol: number[]): number {
  const free = laneLastCol.findIndex((last) => colStart > last);
  if (free !== -1) {
    laneLastCol[free] = -1; // caller sets the real value
    return free;
  }
  laneLastCol.push(-1);
  return laneLastCol.length - 1;
}

function renderWeek(weekStart: Date, spans: EventSpan[], todayKey: string): HTMLElement {
  const weekEl = document.createElement('div');
  weekEl.className = 'mini-cal-week';

  const weekDays: Date[] = [];
  for (let c = 0; c < DAYS_PER_WEEK; c++) {
    const day = new Date(weekStart);
    day.setDate(weekStart.getDate() + c);
    weekDays.push(day);
  }
  const weekFirst = weekDays[0];
  const weekLast = weekDays[DAYS_PER_WEEK - 1];

  // Day-number row (grid row 1)
  for (let c = 0; c < DAYS_PER_WEEK; c++) {
    const day = weekDays[c];
    const numCell = document.createElement('div');
    numCell.className = 'mini-cal-day-num';
    if (toDateKey(day) === todayKey) numCell.classList.add('mini-cal-today');
    numCell.style.gridColumn = String(c + 1);
    numCell.style.gridRow = '1';
    numCell.textContent = String(day.getDate());
    weekEl.appendChild(numCell);
  }

  // Events intersecting this week, earliest (and longest) first for stable lanes.
  const weekEvents = spans
    .filter((s) => s.lastDay >= weekFirst && s.startDay <= weekLast)
    .sort((a, b) => {
      const byStart = a.startDay.getTime() - b.startDay.getTime();
      return byStart !== 0 ? byStart : b.lastDay.getTime() - a.lastDay.getTime();
    });

  const laneLastCol: number[] = [];
  for (const s of weekEvents) {
    const colStart = Math.max(0, dayDiff(s.startDay, weekFirst));
    const colEnd = Math.min(DAYS_PER_WEEK - 1, dayDiff(s.lastDay, weekFirst));
    const lane = assignLane(colStart, laneLastCol);
    laneLastCol[lane] = colEnd;
    if (lane >= MAX_LANES) continue; // cap stacked bars, drop overflow

    const bar = document.createElement('div');
    bar.className = 'mini-cal-bar';
    // grid-column end line is exclusive, so span [colStart+1 .. colEnd+2).
    bar.style.gridColumn = `${colStart + 1} / ${colEnd + 2}`;
    bar.style.gridRow = String(lane + 2);
    bar.style.background = s.ev.color;
    bar.textContent = s.ev.title;
    // Flatten the edge where the event continues into an adjacent week so the
    // bar reads as one continuous range across rows.
    if (s.startDay < weekFirst) bar.classList.add('mini-cal-bar-cont-left');
    if (s.lastDay > weekLast) bar.classList.add('mini-cal-bar-cont-right');
    weekEl.appendChild(bar);
  }

  return weekEl;
}

export function render(events: CalendarEvent[], container: HTMLElement): void {
  container.innerHTML = '';

  const today = new Date();
  const todayKey = toDateKey(today);

  // Start from Monday of the current week.
  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - mondayFirst(today.getDay()));
  weekStart.setHours(0, 0, 0, 0);

  const spans = events.map(eventSpan);

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

  const grid = document.createElement('div');
  grid.className = 'mini-cal-grid';
  for (let w = 0; w < NUM_WEEKS; w++) {
    const wkStart = new Date(weekStart);
    wkStart.setDate(weekStart.getDate() + w * DAYS_PER_WEEK);
    grid.appendChild(renderWeek(wkStart, spans, todayKey));
  }
  container.appendChild(grid);
}

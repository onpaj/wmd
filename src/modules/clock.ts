import { StravaMeals, StravaDay, FavoriteName } from '../types';
import { nameDayParts } from './nameday.ts';

let _soupEl: HTMLElement | null = null;
let _lunchEl: HTMLElement | null = null;
let _marksEl: HTMLElement | null = null;
let _tempEl: HTMLElement | null = null;
let _meals: StravaMeals | null = null;
let _nameDayEl: HTMLElement | null = null;
let _favoriteNames: readonly FavoriteName[] = [];
let _renderedNameDay = '';

const NAME_DAY_PREFIX = 'Svátek: ';
const NAME_SEPARATOR = ', ';

function isBeforeBreakingTime(breakingTime: string): boolean {
  const [h, m] = breakingTime.split(':').map(Number);
  const now = new Date();
  return now.getHours() < h || (now.getHours() === h && now.getMinutes() < m);
}

function renderMarks(day: StravaDay | null): void {
  if (!_marksEl) return;
  _marksEl.innerHTML = '';
  if (!day) return;
  for (const p of day.people) {
    const dot = document.createElement('span');
    dot.className = 'meal-mark';
    dot.title = p.name;
    dot.textContent = p.name.charAt(0).toUpperCase();
    if (p.ordered === true) {
      dot.classList.add('ordered');
      if (p.color) dot.style.background = p.color;
    } else if (p.ordered === false) {
      dot.classList.add('not-ordered');
    } else {
      dot.classList.add('unknown');
    }
    _marksEl.appendChild(dot);
  }
}

function renderMeals(): void {
  if (!_soupEl || !_lunchEl || !_marksEl) return;
  if (!_meals) {
    _soupEl.textContent = '';
    _lunchEl.textContent = '';
    _marksEl.innerHTML = '';
    return;
  }
  const day = isBeforeBreakingTime(_meals.breaking_time) ? _meals.today : _meals.tomorrow;
  _soupEl.textContent  = day?.soup  ?? '';
  _lunchEl.textContent = day?.meal  ?? '';
  renderMarks(day ?? null);
}

/** Rebuilds the name-day line only when its content changes, not on every clock tick. */
function renderNameDay(now: Date): void {
  if (!_nameDayEl) return;
  const parts = nameDayParts(now, _favoriteNames);
  const signature = JSON.stringify(parts);
  if (signature === _renderedNameDay) return;
  _renderedNameDay = signature;

  _nameDayEl.replaceChildren();
  if (parts.length === 0) return;
  _nameDayEl.append(NAME_DAY_PREFIX);
  parts.forEach((part, i) => {
    if (i > 0) _nameDayEl!.append(NAME_SEPARATOR);
    const span = document.createElement('span');
    span.textContent = part.text;
    if (part.isFavorite) span.className = 'nameday-favorite';
    _nameDayEl!.append(span);
  });
}

export function updateFavoriteNames(favorites: readonly FavoriteName[]): void {
  _favoriteNames = favorites;
  renderNameDay(new Date());
}

export function updateMeals(meals: StravaMeals | null): void {
  _meals = meals;
  renderMeals();
}

export function updateTemperature(temp: number | null): void {
  if (!_tempEl) return;
  _tempEl.textContent = temp !== null ? `${temp}°` : '';
}

export function startClock(container: HTMLElement): void {
  const topRowEl = document.createElement('div');
  topRowEl.id = 'clock-top-row';

  _tempEl = document.createElement('div');
  _tempEl.id = 'clock-temp';

  const timeEl = document.createElement('div');
  timeEl.id = 'clock-time';

  topRowEl.append(_tempEl, timeEl);

  const mealsEl = document.createElement('div');
  mealsEl.id = 'clock-meals';

  _nameDayEl = document.createElement('div');
  _nameDayEl.id = 'clock-nameday';

  _marksEl = document.createElement('div');
  _marksEl.id = 'clock-meal-marks';

  const mealTextEl = document.createElement('div');
  mealTextEl.id = 'clock-meal-text';

  _soupEl = document.createElement('div');
  _soupEl.id = 'clock-soup';

  _lunchEl = document.createElement('div');
  _lunchEl.id = 'clock-lunch';

  mealTextEl.append(_soupEl, _lunchEl);
  mealsEl.append(_marksEl, mealTextEl);
  container.append(topRowEl, _nameDayEl, mealsEl);

  function tick(): void {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    timeEl.textContent = `${hh}:${mm}`;
    renderNameDay(now);
    renderMeals();
  }
  tick();
  setInterval(tick, 1000);
}

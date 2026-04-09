import { StravaMeals, StravaDay } from '../types';

let _soupEl: HTMLElement | null = null;
let _lunchEl: HTMLElement | null = null;
let _marksEl: HTMLElement | null = null;
let _tempEl: HTMLElement | null = null;
let _meals: StravaMeals | null = null;

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
  container.append(topRowEl, mealsEl);

  function tick(): void {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    timeEl.textContent = `${hh}:${mm}`;
    renderMeals();
  }
  tick();
  setInterval(tick, 1000);
}

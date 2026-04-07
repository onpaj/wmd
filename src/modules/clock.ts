import { Meals } from '../types';

let _soupEl: HTMLElement | null = null;
let _lunchEl: HTMLElement | null = null;
let _tempEl: HTMLElement | null = null;
let _meals: Meals | null = null;

function isBefore1230(): boolean {
  const now = new Date();
  return now.getHours() < 12 || (now.getHours() === 12 && now.getMinutes() < 30);
}

function renderMeals(): void {
  if (!_soupEl || !_lunchEl) return;
  if (!_meals) {
    _soupEl.textContent = '';
    _lunchEl.textContent = '';
    return;
  }
  const showToday = isBefore1230();
  _soupEl.textContent = showToday ? _meals.soup_today : _meals.soup_tomorrow;
  _lunchEl.textContent = showToday ? _meals.lunch_today : _meals.lunch_tomorrow;
}

export function updateMeals(meals: Meals | null): void {
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

  _soupEl = document.createElement('div');
  _soupEl.id = 'clock-soup';
  _lunchEl = document.createElement('div');
  _lunchEl.id = 'clock-lunch';
  mealsEl.append(_soupEl, _lunchEl);

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

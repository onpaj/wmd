import type { CarStatus } from '../types';

const LOW_BATTERY_PERCENT = 20;
const CAR_ICON = '🚗';
const CHARGING_ICON = '⚡';
const PLUGGED_ICON = '🔌';

export interface CarView {
  battery: string;
  range: string;
  isLow: boolean;
}

/** Charging implies plugged in, so the bolt wins; nothing is shown when the cable is out. */
function cableIcon(car: CarStatus): string {
  if (car.is_charging) return CHARGING_ICON;
  return car.is_plugged_in ? PLUGGED_ICON : '';
}

export function formatCar(car: CarStatus | null): CarView | null {
  if (!car) return null;
  return {
    battery: `${cableIcon(car)}${Math.round(car.battery_percent)} %`,
    range: car.range_km !== null ? `${Math.round(car.range_km)} km` : '—',
    isLow: car.battery_percent < LOW_BATTERY_PERCENT,
  };
}

/** Renders the car as one more tile in the garden-temps row, reusing its icon/value/secondary layout. */
export function render(car: CarStatus | null, container: HTMLElement): void {
  container.innerHTML = '';
  const view = formatCar(car);
  if (!view) return;

  const item = document.createElement('div');
  item.className = 'garden-temp-item';

  const icon = document.createElement('div');
  icon.className = 'garden-temp-icon';
  icon.textContent = CAR_ICON;

  const battery = document.createElement('div');
  battery.className = 'garden-temp-value';
  if (view.isLow) battery.classList.add('car-battery-low');
  battery.textContent = view.battery;

  const range = document.createElement('div');
  range.className = 'garden-temp-humidity';
  range.textContent = view.range;

  item.append(icon, battery, range);
  container.appendChild(item);
}

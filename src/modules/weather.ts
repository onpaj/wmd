import { WeatherDay } from '../types';

const CZECH_DAYS = ['ne', 'po', 'út', 'st', 'čt', 'pá', 'so'];

const ICON_MAP: Record<string, string> = {
  sunny: '☀️',
  'partly-cloudy': '⛅',
  cloudy: '☁️',
  rainy: '🌧',
  'heavy-rain': '⛈',
  snow: '❄️',
  storm: '⛈',
  fog: '🌫',
};

function getIcon(iconKey: string): string {
  return ICON_MAP[iconKey] ?? '🌡';
}

export function render(days: WeatherDay[], container: HTMLElement): void {
  container.innerHTML = '';

  for (const day of days) {
    const date = new Date(day.date);
    const weekday = CZECH_DAYS[date.getUTCDay()];

    const col = document.createElement('div');
    col.className = 'weather-day';

    const dayLabel = document.createElement('div');
    dayLabel.className = 'weather-weekday';
    dayLabel.textContent = weekday;

    const icon = document.createElement('div');
    icon.className = 'weather-icon';
    icon.textContent = getIcon(day.icon);

    const high = document.createElement('div');
    high.className = 'weather-high';
    high.textContent = `${Math.round(day.temp_high)}°`;

    const low = document.createElement('div');
    low.className = 'weather-low';
    low.textContent = `${Math.round(day.temp_low)}°`;

    const precip = document.createElement('div');
    precip.className = 'weather-precip';
    precip.textContent = `${Math.round(day.precip_percent)}%`;

    col.appendChild(dayLabel);
    col.appendChild(icon);
    col.appendChild(high);
    col.appendChild(low);
    col.appendChild(precip);
    container.appendChild(col);
  }
}

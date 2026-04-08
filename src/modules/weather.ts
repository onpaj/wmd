import { WeatherDay, GardenTemps } from '../types';

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

const GARDEN_SENSORS: { key: keyof GardenTemps; icon: string; label: string }[] = [
  { key: 'glasshouse', icon: '🪴', label: 'Skleník' },
  { key: 'coop',       icon: '🐔', label: 'Kurník' },
  { key: 'brooder',    icon: '🐣', label: 'Líheň' },
];

function getIcon(iconKey: string): string {
  return ICON_MAP[iconKey] ?? '🌡';
}

export function render(days: WeatherDay[], gardenTemps: GardenTemps | null, container: HTMLElement): void {
  container.innerHTML = '';

  // Garden temps row
  if (gardenTemps) {
    const row = document.createElement('div');
    row.className = 'garden-temps';

    for (const sensor of GARDEN_SENSORS) {
      const val = gardenTemps[sensor.key];
      const item = document.createElement('div');
      item.className = 'garden-temp-item';

      const icon = document.createElement('div');
      icon.className = 'garden-temp-icon';
      icon.textContent = sensor.icon;

      const label = document.createElement('div');
      label.className = 'garden-temp-label';
      label.textContent = sensor.label;

      const value = document.createElement('div');
      value.className = 'garden-temp-value';
      value.textContent = val !== null ? `${Math.round(val)}°` : '—';

      item.appendChild(icon);
      item.appendChild(label);
      item.appendChild(value);
      row.appendChild(item);
    }

    container.appendChild(row);
  }

  // Weather forecast row
  const forecast = document.createElement('div');
  forecast.className = 'weather-forecast';

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
    forecast.appendChild(col);
  }

  container.appendChild(forecast);
}

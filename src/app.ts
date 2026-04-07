import { fetchData } from './api';
import { DashboardData } from './types';
import { startClock } from './modules/clock';
import { render as renderPhotos } from './modules/photo';
import { render as renderCalendar } from './modules/calendar';
import { render as renderWeather } from './modules/weather';
import { render as renderMiniCal } from './modules/mini-calendar';

function update(data: DashboardData): void {
  renderPhotos(data.photos, document.getElementById('photo-area')!, data.photo_interval_seconds);
  renderCalendar(data.events, document.getElementById('calendar-area')!);
  renderWeather(data.weather, document.getElementById('weather-area')!);
  renderMiniCal(data.events, document.getElementById('mini-cal-area')!);

  const haArea = document.getElementById('ha-area')!;
  if (data.ha_entities.length > 0) {
    haArea.style.display = 'flex';
    haArea.innerHTML = data.ha_entities
      .map(e => `<span>${e.label}: ${e.state} ${e.unit}</span>`)
      .join('');
  } else {
    haArea.style.display = 'none';
  }
}

async function init(): Promise<void> {
  startClock(document.getElementById('clock-area')!);
  const data = await fetchData();
  update(data);
  setInterval(async () => {
    try {
      const fresh = await fetchData();
      update(fresh);
    } catch (err) {
      console.error(err);
    }
  }, 60000);
}

init().catch(console.error);

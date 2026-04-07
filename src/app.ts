import { fetchData } from './api';
import { startClock } from './modules/clock';
import { render as renderPhotos } from './modules/photo';
import { render as renderCalendar } from './modules/calendar';
import { render as renderWeather } from './modules/weather';

startClock(document.getElementById('clock-area')!);

async function init(): Promise<void> {
  const data = await fetchData();
  console.log('Dashboard data loaded', data.server_time);
  renderPhotos(data.photos, document.getElementById('photo-area')!, data.photo_interval_seconds);
  renderCalendar(data.events, document.getElementById('calendar-area')!);
  renderWeather(data.weather, document.getElementById('weather-area')!);
}

init().catch(console.error);

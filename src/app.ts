import { fetchData } from './api';
import { startClock } from './modules/clock';
import { render as renderPhotos } from './modules/photo';

startClock(document.getElementById('clock-area')!);

async function init(): Promise<void> {
  const data = await fetchData();
  console.log('Dashboard data loaded', data.server_time);
  renderPhotos(data.photos, document.getElementById('photo-area')!, data.photo_interval_seconds);
}

init().catch(console.error);

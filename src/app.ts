import { fetchData } from './api';
import { startClock } from './modules/clock';

startClock(document.getElementById('clock-area')!);

async function init(): Promise<void> {
  const data = await fetchData();
  console.log('Dashboard data loaded', data.server_time);
}

init().catch(console.error);

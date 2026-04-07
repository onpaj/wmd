import { fetchData } from './api';

async function init(): Promise<void> {
  const data = await fetchData();
  console.log('Dashboard data loaded', data.server_time);
}

init().catch(console.error);

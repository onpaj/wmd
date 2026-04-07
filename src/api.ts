import { DashboardData } from './types';

export async function fetchData(): Promise<DashboardData> {
  const response = await fetch('/api/data');
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard data: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<DashboardData>;
}

export interface Photo {
  id: string;
  url: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  calendar_name: string;
  color: string;
}

export interface WeatherDay {
  date: string;
  icon: string;
  temp_high: number;
  temp_low: number;
  precip_percent: number;
}

export interface HaEntity {
  id: string;
  label: string;
  state: string;
  unit: string;
}

export interface DashboardData {
  photos: Photo[];
  events: CalendarEvent[];
  weather: WeatherDay[];
  ha_entities: HaEntity[];
  photo_interval_seconds: number;
  server_time: string;
}
